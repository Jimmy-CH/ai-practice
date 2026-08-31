
import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """HTTP 请求日志中间件，自动记录请求/响应信息"""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # 提取客户端 IP
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000

            log_data = {
                "method": method,
                "path": path,
                "client_ip": client_ip,
                "status_code": response.status_code,
                "process_time_ms": round(process_time, 2),
            }

            if response.status_code >= 500:
                logger.error("请求处理异常", extra=log_data)
            elif response.status_code >= 400:
                logger.warning("请求客户端错误", extra=log_data)
            else:
                logger.info("请求处理完成", extra=log_data)

            # 添加响应头记录耗时
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            return response

        except Exception as exc:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                "请求处理异常",
                extra={
                    "method": method,
                    "path": path,
                    "client_ip": client_ip,
                    "process_time_ms": round(process_time, 2),
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise
