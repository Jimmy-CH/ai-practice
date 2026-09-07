"""数据源模型 - 用户上传的 CSV/Excel 数据。"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(100), unique=True, nullable=False)  # SQLite 表名
    original_filename = Column(String(255), nullable=False)  # 原始文件名
    description = Column(Text, default="")  # 表级中文描述
    row_count = Column(Integer, default=0)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    columns = relationship("DataSourceColumn", back_populates="data_source", cascade="all, delete-orphan")


class DataSourceColumn(Base):
    __tablename__ = "data_source_columns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    column_name = Column(String(100), nullable=False)
    column_type = Column(String(50), nullable=False)  # TEXT, INTEGER, REAL
    description = Column(Text, default="")  # 列级中文描述

    data_source = relationship("DataSource", back_populates="columns")
