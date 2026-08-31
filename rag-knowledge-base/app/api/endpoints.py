# app/api/endpoints.py
import time
import uuid
import shutil
import os
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.core.rag_pipeline import rag_engine

router = APIRouter()
UPLOAD_DIR = "./uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """接收文件并触发后台异步解析任务"""
    ALLOWED_EXTENSIONS = {".pdf", ".txt"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 PDF 和 TXT 格式")

    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 将耗时的解析与向量化任务放入后台执行，避免阻塞 API 响应
    background_tasks.add_task(rag_engine.ingest_document, file_path)

    return {"status": "processing", "filename": file.filename, "message": "文档已接收，正在后台解析入库"}


@router.post("/v1/ask")
async def ask_knowledge_base(payload: dict):
    """核心问答接口"""
    question = payload.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="提问内容不能为空")

    start_time = time.time()
    try:
        result = rag_engine.ask(question)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        result["latency_ms"] = latency_ms
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答生成失败: {str(e)}")

