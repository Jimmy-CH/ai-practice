from typing import List, Optional
from pydantic import BaseModel


class HistoryMessage(BaseModel):
    role: str   # "user" | "agent"
    content: str


class AgentQueryRequest(BaseModel):
    question: str
    history: List[HistoryMessage] = []


class AgentStepResponse(BaseModel):
    type: str      # "thought" | "action" | "observation"
    content: str


class ChartData(BaseModel):
    type: str          # "bar" | "line" | "pie"
    title: str
    x_axis: List[str]
    series: List[dict]


class AgentQueryResponse(BaseModel):
    answer: str
    steps: List[AgentStepResponse]
    success: bool
    chart_data: Optional[ChartData] = None
    suggestions: List[str] = []


class TableSchema(BaseModel):
    table_name: str
    columns: List[dict]


class SchemasResponse(BaseModel):
    tables: List[TableSchema]


class DashboardSummary(BaseModel):
    total_revenue: float
    total_orders: int
    total_products: int
    monthly_revenue: float


class DashboardTrend(BaseModel):
    dates: List[str]
    values: List[float]


class DashboardCategory(BaseModel):
    labels: List[str]
    values: List[float]


class DashboardTopProducts(BaseModel):
    names: List[str]
    values: List[float]


class DashboardResponse(BaseModel):
    summary: DashboardSummary
    daily_trend: DashboardTrend
    category_distribution: DashboardCategory
    top_products: DashboardTopProducts
