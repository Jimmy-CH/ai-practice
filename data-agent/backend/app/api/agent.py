from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text as sql_text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.agent import (
    AgentQueryRequest, AgentQueryResponse, AgentStepResponse,
    SchemasResponse, TableSchema, ChartData,
    DashboardResponse, DashboardSummary, DashboardTrend,
    DashboardCategory, DashboardTopProducts,
)
from app.agent.langchain_agent import run_agent, stream_agent
from app.auth.dependencies import require_role
from app.users.models import User
from app.database import sync_engine, get_db
from app.models.datasource import DataSource

router = APIRouter(prefix="/agent", tags=["Agent"])

DB_SCHEMA = [
    TableSchema(
        table_name="products",
        columns=[
            {"name": "id", "type": "INTEGER", "description": "商品ID"},
            {"name": "name", "type": "TEXT", "description": "商品名称"},
            {"name": "category", "type": "TEXT", "description": "商品品类"},
            {"name": "price", "type": "REAL", "description": "商品价格"},
            {"name": "created_at", "type": "DATETIME", "description": "创建时间"},
        ],
    ),
    TableSchema(
        table_name="orders",
        columns=[
            {"name": "id", "type": "INTEGER", "description": "订单ID"},
            {"name": "customer_name", "type": "TEXT", "description": "客户姓名"},
            {"name": "order_date", "type": "DATE", "description": "订单日期"},
            {"name": "status", "type": "TEXT", "description": "订单状态"},
        ],
    ),
    TableSchema(
        table_name="order_items",
        columns=[
            {"name": "id", "type": "INTEGER", "description": "明细ID"},
            {"name": "order_id", "type": "INTEGER", "description": "订单ID(外键)"},
            {"name": "product_id", "type": "INTEGER", "description": "商品ID(外键)"},
            {"name": "quantity", "type": "INTEGER", "description": "数量"},
            {"name": "unit_price", "type": "REAL", "description": "单价"},
        ],
    ),
]


async def _get_user_tables(db: AsyncSession, user_id: int) -> list:
    """获取用户的所有数据源表结构信息。"""
    query = (
        select(DataSource)
        .where(DataSource.uploaded_by == user_id)
        .options(selectinload(DataSource.columns))
    )
    result = await db.execute(query)
    sources = result.scalars().all()
    return [
        {
            "table_name": ds.table_name,
            "description": ds.description or "",
            "columns": [
                {
                    "column_name": c.column_name,
                    "column_type": c.column_type,
                    "description": c.description or "",
                }
                for c in ds.columns
            ],
        }
        for ds in sources
    ]


@router.post("/query", response_model=AgentQueryResponse)
async def query(
    request: AgentQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    """提交自然语言问题，Agent 执行 ReAct 循环后返回结果。"""
    user_tables = await _get_user_tables(db, current_user.id)
    result = await run_agent(request.question, [h.dict() for h in request.history], user_tables)
    return AgentQueryResponse(
        answer=result.answer,
        steps=[AgentStepResponse(type=s.type, content=s.content) for s in result.steps],
        success=result.success,
        chart_data=ChartData(**result.chart_data) if result.chart_data else None,
        suggestions=result.suggestions,
    )


@router.post("/query/stream")
async def query_stream(
    request: Request,
    req: AgentQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    """SSE 流式查询。"""
    user_tables = await _get_user_tables(db, current_user.id)
    return StreamingResponse(
        stream_agent(req.question, request, [h.dict() for h in req.history], user_tables),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/schemas", response_model=SchemasResponse)
async def get_schemas(
    _current_user: User = Depends(require_role("admin", "editor", "viewer")),
):
    """获取数据库表结构信息。"""
    return SchemasResponse(tables=DB_SCHEMA)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    _current_user: User = Depends(require_role("admin", "editor")),
):
    """获取仪表盘聚合数据。"""
    with sync_engine.connect() as conn:
        # 汇总统计
        summary_rows = conn.execute(sql_text("""
            SELECT
                COALESCE(SUM(oi.quantity * oi.unit_price), 0) as total_revenue,
                COUNT(DISTINCT o.id) as total_orders,
                (SELECT COUNT(*) FROM products) as total_products,
                COALESCE(SUM(CASE WHEN o.order_date >= date('now', '-30 days')
                    THEN oi.quantity * oi.unit_price ELSE 0 END), 0) as monthly_revenue
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
        """)).fetchone()

        # 近 30 天每日趋势
        trend_rows = conn.execute(sql_text("""
            SELECT date(o.order_date) as d,
                   SUM(oi.quantity * oi.unit_price) as revenue
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            WHERE o.order_date >= date('now', '-30 days')
            GROUP BY date(o.order_date)
            ORDER BY d
        """)).fetchall()

        # 品类分布
        cat_rows = conn.execute(sql_text("""
            SELECT p.category, SUM(oi.quantity * oi.unit_price) as revenue
            FROM products p
            JOIN order_items oi ON oi.product_id = p.id
            GROUP BY p.category
            ORDER BY revenue DESC
        """)).fetchall()

        # TOP 10 热销商品
        top_rows = conn.execute(sql_text("""
            SELECT p.name, SUM(oi.quantity) as qty
            FROM products p
            JOIN order_items oi ON oi.product_id = p.id
            GROUP BY p.id
            ORDER BY qty DESC
            LIMIT 10
        """)).fetchall()

    return DashboardResponse(
        summary=DashboardSummary(
            total_revenue=summary_rows[0] or 0,
            total_orders=summary_rows[1] or 0,
            total_products=summary_rows[2] or 0,
            monthly_revenue=summary_rows[3] or 0,
        ),
        daily_trend=DashboardTrend(
            dates=[str(r[0]) for r in trend_rows],
            values=[float(r[1]) for r in trend_rows],
        ),
        category_distribution=DashboardCategory(
            labels=[r[0] for r in cat_rows],
            values=[float(r[1]) for r in cat_rows],
        ),
        top_products=DashboardTopProducts(
            names=[r[0] for r in top_rows],
            values=[float(r[1]) for r in top_rows],
        ),
    )
