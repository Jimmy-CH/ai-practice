"""请求日志中间件：方法/路径/IP/脱敏后的请求体/耗时 一行式访问日志。"""
import json
import logging
import time

from fastapi import FastAPI, Request

SENSITIVE_KEYS = {"password", "token", "access_token", "refresh_token", "api_key", "authorization"}
BODY_LOG_MAX_LENGTH = 500

logger = logging.getLogger("app.middleware.request_log")


def _sanitize_body(raw: bytes, content_type: str) -> str:
    """将请求体转为可安全打印的文本，敏感字段与表单数据脱敏，超长截断。"""
    if not raw:
        return ""
    if content_type.startswith("application/x-www-form-urlencoded") or content_type.startswith("multipart/form-data"):
        return "<form-data redacted>"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "<binary>"
    if content_type.startswith("application/json"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = {
                    key: ("***" if key.lower() in SENSITIVE_KEYS else value)
                    for key, value in data.items()
                }
            text = json.dumps(data, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pass
    if len(text) > BODY_LOG_MAX_LENGTH:
        return text[:BODY_LOG_MAX_LENGTH] + f"...(truncated, total {len(text)} chars)"
    return text


def register_request_log_middleware(app: FastAPI) -> None:
    """把请求耗时日志中间件挂到 app（main 组装层调用）。"""

    @app.middleware("http")
    async def log_request_duration(request: Request, call_next):
        start = time.perf_counter()
        method = request.method
        path = request.url.path
        query = request.url.query
        client_ip = request.client.host if request.client else "-"
        content_type = request.headers.get("content-type", "")
        body_preview = ""
        if method in ("POST", "PUT", "PATCH"):
            raw_body = await request.body()
            body_preview = _sanitize_body(raw_body, content_type)
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        suffix = f"?{query}" if query else ""
        body_part = f" body={body_preview}" if body_preview else ""
        logger.info(
            f"[{method}] {path}{suffix} ip={client_ip}{body_part} "
            f"-> {response.status_code} ({duration_ms:.2f}ms)"
        )
        return response
