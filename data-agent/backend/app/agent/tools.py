"""Agent 工具定义：SQL 只读查询。"""
from sqlalchemy import create_engine, text
from langchain_core.tools import tool
from app.config import settings

# 同步引擎供工具使用
SYNC_DB_URL = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+aiomysql", "")
sync_engine = create_engine(SYNC_DB_URL)

FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]


def _check_sql_safety(query: str) -> str | None:
    """检查 SQL 是否安全。返回 None 表示安全，否则返回错误信息。"""
    cleaned = query.strip().upper()
    if not cleaned.startswith("SELECT"):
        return "安全错误：只允许 SELECT 查询"
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in cleaned:
            return f"安全错误：禁止使用 {keyword} 语句"
    return None


@tool
def sql_query(query: str) -> str:
    """执行只读 SQL 查询。输入为 SELECT 语句，返回查询结果的文本表格。
    可用表：products(id, name, category, price, created_at),
    orders(id, customer_name, order_date, status),
    order_items(id, order_id, product_id, quantity, unit_price)
    """
    safety_error = _check_sql_safety(query)
    if safety_error:
        return safety_error

    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())
            rows = result.fetchall()

            if not rows:
                return "查询结果为空"

            # 格式化为文本表格
            header = " | ".join(columns)
            separator = "-" * len(header)
            lines = [header, separator]
            for row in rows[:50]:  # 限制最多返回 50 行
                lines.append(" | ".join(str(v) for v in row))

            if len(rows) > 50:
                lines.append(f"... (共 {len(rows)} 行，仅显示前 50 行)")

            return "\n".join(lines)

    except Exception as e:
        return f"SQL 执行错误: {str(e)}"
