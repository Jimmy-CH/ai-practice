# app/api/endpoints.py
import asyncio
import time
import uuid
import shutil
import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.api.schemas import AskRequest, AskResponse, UploadResponse
from app.core.rag_pipeline import get_rag_engine

logger = logging.getLogger("RAG_API")

router = APIRouter()
UPLOAD_DIR = "./uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

# 语义缓存（可选，Redis 不可用时自动降级）
try:
    from app.core.cache import semantic_cache
    _cache_available = True
except Exception:
    semantic_cache = None
    _cache_available = False
    logger.warning("语义缓存不可用，将以无缓存模式运行")


@router.post("/upload", response_model=UploadResponse)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """接收文件并触发后台异步解析任务"""
    ALLOWED_EXTENSIONS = {".pdf", ".txt"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 PDF 和 TXT 格式")

    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")

    # 先写入临时文件并校验大小，避免超大文件耗尽磁盘
    tmp_path = file_path + ".tmp"
    try:
        with open(tmp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if os.path.getsize(tmp_path) > MAX_UPLOAD_SIZE:
            os.unlink(tmp_path)
            raise HTTPException(status_code=413, detail=f"文件大小超出限制（最大 {MAX_UPLOAD_SIZE // (1024*1024)}MB）")

        os.rename(tmp_path, file_path)
    except HTTPException:
        raise
    except Exception as e:
        # 清理可能残留的临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        logger.error(f"文件保存失败: {e}")
        raise HTTPException(status_code=500, detail="文件保存失败")

    # 将耗时的解析与向量化任务放入后台执行，避免阻塞 API 响应
    rag_engine = get_rag_engine()
    background_tasks.add_task(rag_engine.ingest_document, file_path)

    return UploadResponse(
        status="processing",
        filename=file.filename,
        message="文档已接收，正在后台解析入库",
    )


@router.post("/v1/ask", response_model=AskResponse)
async def ask_knowledge_base(payload: AskRequest):
    """核心问答接口：支持语义缓存加速"""
    # 尝试从语义缓存获取
    if _cache_available:
        cached = semantic_cache.get(payload.question)
        if cached:
            return AskResponse(**cached)

    start_time = time.time()
    try:
        rag_engine = get_rag_engine()
        # 使用 asyncio.to_thread 将同步阻塞调用放入线程池，避免阻塞事件循环
        result = await asyncio.to_thread(rag_engine.ask, payload.question, top_k=payload.top_k)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        result["latency_ms"] = latency_ms

        # 写入缓存
        if _cache_available:
            semantic_cache.set(payload.question, result)

        return AskResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"问答生成失败: {e}")
        raise HTTPException(status_code=500, detail="问答生成失败，请稍后重试")
