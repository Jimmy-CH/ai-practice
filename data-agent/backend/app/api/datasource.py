"""数据源管理 API。"""
import csv
import io
import re
import logging
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, sync_engine
from app.auth.dependencies import get_current_user
from app.users.models import User
from app.models.datasource import DataSource, DataSourceColumn
from app.schemas.datasource import (
    DataSourceOut, DataSourceListOut, DataSourceUpdate, ColumnInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasource", tags=["DataSource"])


def _sanitize_table_name(filename: str) -> str:
    """将文件名转换为合法的 SQLite 表名。"""
    name = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff]", "_", filename.rsplit(".", 1)[0])
    name = name.strip("_")
    if not name or name[0].isdigit():
        name = "ds_" + name
    return name[:80]


def _infer_sqlite_type(value: str) -> str:
    """推断 SQLite 列类型。"""
    try:
        int(value)
        return "INTEGER"
    except ValueError:
        pass
    try:
        float(value)
        return "REAL"
    except ValueError:
        pass
    return "TEXT"


@router.post("/upload", response_model=DataSourceOut)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传 CSV/Excel 文件，自动建表。"""
    filename = file.filename or "unknown"
    if not filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "仅支持 CSV、XLSX、XLS 格式")

    content = await file.read()
    table_name = _sanitize_table_name(filename)

    # 检查表名是否已存在
    existing = await db.execute(select(DataSource).where(DataSource.table_name == table_name))
    if existing.scalar_one_or_none():
        table_name = f"{table_name}_{current_user.id}"

    # 解析 CSV
    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_content = content.decode("gbk", errors="replace")

    reader = csv.reader(io.StringIO(text_content))
    rows = list(reader)

    if len(rows) < 2:
        raise HTTPException(400, "文件至少需要包含表头和一行数据")

    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]

    # 推断列类型
    col_types = []
    for i, header in enumerate(headers):
        sample_values = [row[i] for row in data_rows[:20] if i < len(row) and row[i].strip()]
        if sample_values:
            col_types.append(_infer_sqlite_type(sample_values[0]))
        else:
            col_types.append("TEXT")

    # 在 SQLite 中创建表
    col_defs = ", ".join(f'"{h}" {t}' for h, t in zip(headers, col_types))
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})'

    with sync_engine.connect() as conn:
        conn.execute(sql_text(create_sql))
        # 插入数据
        placeholders = ", ".join(f":{i}" for i in range(len(headers)))
        insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
        for row in data_rows:
            if len(row) >= len(headers):
                params = {str(i): row[i].strip() for i in range(len(headers))}
                conn.execute(sql_text(insert_sql), params)
        conn.commit()

    # 注册到 data_sources
    ds = DataSource(
        table_name=table_name,
        original_filename=filename,
        row_count=len(data_rows),
        uploaded_by=current_user.id,
    )
    for i, header in enumerate(headers):
        col = DataSourceColumn(
            column_name=header,
            column_type=col_types[i],
            description="",
        )
        ds.columns.append(col)

    db.add(ds)
    await db.commit()
    await db.refresh(ds)

    logger.info(f"用户 {current_user.username} 上传数据源: {table_name} ({len(data_rows)} 行)")

    return DataSourceOut(
        id=ds.id,
        table_name=ds.table_name,
        original_filename=ds.original_filename,
        description=ds.description or "",
        row_count=ds.row_count,
        columns=[ColumnInfo(column_name=c.column_name, column_type=c.column_type, description=c.description or "") for c in ds.columns],
        created_at=ds.created_at,
    )


@router.get("/", response_model=DataSourceListOut)
async def list_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户上传的数据源列表。"""
    query = (
        select(DataSource)
        .where(DataSource.uploaded_by == current_user.id)
        .options(selectinload(DataSource.columns))
        .order_by(DataSource.created_at.desc())
    )
    result = await db.execute(query)
    sources = result.scalars().all()

    return DataSourceListOut(
        sources=[
            DataSourceOut(
                id=ds.id,
                table_name=ds.table_name,
                original_filename=ds.original_filename,
                description=ds.description or "",
                row_count=ds.row_count,
                columns=[ColumnInfo(column_name=c.column_name, column_type=c.column_type, description=c.description or "") for c in ds.columns],
                created_at=ds.created_at,
            )
            for ds in sources
        ]
    )


@router.put("/{source_id}", response_model=DataSourceOut)
async def update_source(
    source_id: int,
    update: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新数据源描述和列描述。"""
    query = (
        select(DataSource)
        .where(DataSource.id == source_id, DataSource.uploaded_by == current_user.id)
        .options(selectinload(DataSource.columns))
    )
    result = await db.execute(query)
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "数据源不存在")

    if update.description is not None:
        ds.description = update.description

    if update.column_descriptions:
        col_map = {c.column_name: c for c in ds.columns}
        for item in update.column_descriptions:
            col_name = item.get("column_name")
            desc = item.get("description", "")
            if col_name in col_map:
                col_map[col_name].description = desc

    await db.commit()
    await db.refresh(ds)

    return DataSourceOut(
        id=ds.id,
        table_name=ds.table_name,
        original_filename=ds.original_filename,
        description=ds.description or "",
        row_count=ds.row_count,
        columns=[ColumnInfo(column_name=c.column_name, column_type=c.column_type, description=c.description or "") for c in ds.columns],
        created_at=ds.created_at,
    )


@router.delete("/{source_id}")
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除数据源（同时删除 SQLite 表）。"""
    query = select(DataSource).where(
        DataSource.id == source_id, DataSource.uploaded_by == current_user.id
    )
    result = await db.execute(query)
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "数据源不存在")

    # 删除 SQLite 表
    with sync_engine.connect() as conn:
        conn.execute(sql_text(f'DROP TABLE IF EXISTS "{ds.table_name}"'))
        conn.commit()

    await db.delete(ds)
    await db.commit()

    logger.info(f"用户 {current_user.username} 删除数据源: {ds.table_name}")
    return {"detail": "已删除"}
