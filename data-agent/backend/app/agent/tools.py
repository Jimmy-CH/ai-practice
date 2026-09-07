"""Agent 工具定义：SQL 只读查询 + 图表生成。"""
import json
import logging
from sqlalchemy import text
from langchain_core.tools import tool
from app.database import sync_engine

logger = logging.getLogger(__name__)

FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]


def _check_sql_safety(query: str) -> str | None:
    """检查 SQL 是否安全。返回 None 表示安全，否则返回错误信息。"""
    cleaned = query.strip().upper()
    if not cleaned.startswith("SELECT"):
        logger.warning(f"SQL 安全检查失败：非 SELECT 语句: {query[:50]}")
        return "安全错误：只允许 SELECT 查询"
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in cleaned:
            logger.warning(f"SQL 安全检查失败：包含禁止关键字 {keyword}: {query[:50]}")
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
                logger.info(f"SQL 查询结果为空: {query[:50]}")
                return "查询结果为空"

            # 格式化为文本表格
            header = " | ".join(columns)
            separator = "-" * len(header)
            lines = [header, separator]
            for row in rows[:50]:  # 限制最多返回 50 行
                lines.append(" | ".join(str(v) for v in row))

            if len(rows) > 50:
                lines.append(f"... (共 {len(rows)} 行，仅显示前 50 行)")

            logger.info(f"SQL 查询成功，返回 {len(rows)} 行: {query[:50]}")
            return "\n".join(lines)

    except Exception as e:
        logger.error(f"SQL 执行错误: {e}, 查询: {query[:100]}")
        return f"SQL 执行错误: {str(e)}"


@tool
def generate_chart(config_json: str) -> str:
    """生成数据可视化图表配置。
    config_json: JSON 字符串，包含以下字段：
      - chart_type: 图表类型，必须是 "bar"、"line"、"pie" 之一
      - title: 图表标题
      - labels: JSON 数组字符串，如 '["电子产品","服装","食品"]'
      - values: JSON 数组字符串，如 '[15000,8000,5000]'
    示例输入: {"chart_type": "bar", "title": "销量统计", "labels": '["A","B"]', "values": '[10,20]'}
    返回图表配置的 JSON 字符串。
    """
    try:
        config = json.loads(config_json)
    except (json.JSONDecodeError, TypeError):
        return "错误：config_json 必须是合法的 JSON 字符串"

    chart_type = config.get("chart_type", "")
    title = config.get("title", "")
    labels = config.get("labels", "")
    values = config.get("values", "")

    if not title:
        return "错误：缺少 title 字段"
    if chart_type not in ("bar", "line", "pie"):
        return "错误：chart_type 必须是 bar、line 或 pie"
    try:
        labels_list = json.loads(labels)
        values_list = json.loads(values)
    except (json.JSONDecodeError, TypeError):
        return "错误：labels 和 values 必须是合法的 JSON 数组"

    chart_config = {
        "type": chart_type,
        "title": title,
        "x_axis": labels_list,
        "series": [{"name": title, "data": values_list}],
    }
    return json.dumps(chart_config, ensure_ascii=False)
