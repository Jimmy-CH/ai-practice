"""数据源相关 Schema。"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class ColumnInfo(BaseModel):
    column_name: str
    column_type: str
    description: str = ""


class DataSourceOut(BaseModel):
    id: int
    table_name: str
    original_filename: str
    description: str
    row_count: int
    columns: List[ColumnInfo]
    created_at: datetime

    class Config:
        from_attributes = True


class DataSourceUpdate(BaseModel):
    description: Optional[str] = None
    column_descriptions: Optional[List[dict]] = None  # [{"column_name": "xxx", "description": "xxx"}]


class DataSourceListOut(BaseModel):
    sources: List[DataSourceOut]
