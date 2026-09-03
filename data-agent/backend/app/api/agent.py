from fastapi import APIRouter, Depends
from app.schemas.agent import (
    AgentQueryRequest, AgentQueryResponse, AgentStepResponse,
    SchemasResponse, TableSchema
)
from app.agent.langchain_agent import run_agent
from app.auth.dependencies import require_role
from app.users.models import User

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


@router.post("/query", response_model=AgentQueryResponse)
async def query(
    request: AgentQueryRequest,
    _current_user: User = Depends(require_role("admin", "editor")),
):
    """提交自然语言问题，Agent 执行 ReAct 循环后返回结果。"""
    result = await run_agent(request.question)
    return AgentQueryResponse(
        answer=result.answer,
        steps=[AgentStepResponse(type=s.type, content=s.content) for s in result.steps],
        success=result.success,
    )


@router.get("/schemas", response_model=SchemasResponse)
async def get_schemas(
    _current_user: User = Depends(require_role("admin", "editor", "viewer")),
):
    """获取数据库表结构信息。"""
    return SchemasResponse(tables=DB_SCHEMA)
