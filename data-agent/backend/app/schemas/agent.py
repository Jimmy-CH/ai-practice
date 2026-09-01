from typing import List
from pydantic import BaseModel


class AgentQueryRequest(BaseModel):
    question: str


class AgentStepResponse(BaseModel):
    type: str      # "thought" | "action" | "observation"
    content: str


class AgentQueryResponse(BaseModel):
    answer: str
    steps: List[AgentStepResponse]
    success: bool


class TableSchema(BaseModel):
    table_name: str
    columns: List[dict]


class SchemasResponse(BaseModel):
    tables: List[TableSchema]
