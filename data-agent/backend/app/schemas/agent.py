from typing import List, Optional
from pydantic import BaseModel


class AgentQueryRequest(BaseModel):
    question: str


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


class TableSchema(BaseModel):
    table_name: str
    columns: List[dict]


class SchemasResponse(BaseModel):
    tables: List[TableSchema]
