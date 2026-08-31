
import logging
import sys
import json
from datetime import datetime, timezone
from typing import Optional

from app.config import settings


class JsonFormatter(logging.Formatter):
    """JSON 结构化日志格式，适用于生产环境"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 提取 extra 字段
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated",
            "exc_info", "exc_text", "stack_info", "lineno", "pathname",
            "filename", "module", "funcName", "levelname", "levelno",
            "msecs", "pathname", "process", "processName", "thread",
            "threadName", "message",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_data["exception"] = record.exc_text

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """彩色可读日志格式，适用于开发环境"""

    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        color = self.COLORS.get(record.levelname, "")

        base = f"{timestamp} | {color}{level}{self.RESET} | {record.name} | {record.getMessage()}"

        # 附加 extra 字段
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated",
            "exc_info", "exc_text", "stack_info", "lineno", "pathname",
            "filename", "module", "funcName", "levelname", "levelno",
            "msecs", "pathname", "process", "processName", "thread",
            "threadName", "message",
        }
        extra_parts = []
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                extra_parts.append(f"{key}={value}")
        if extra_parts:
            base += " | " + " ".join(extra_parts)

        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)

        return base


def setup_logger(extra_handlers: Optional[list] = None) -> logging.Logger:
    """
    初始化日志系统

    Args:
        extra_handlers: 额外的 Handler 列表（如 ELK、Loki 等）

    Returns:
        配置好的根 logger
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    log_format = settings.LOG_FORMAT.lower()

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有 handler，避免重复配置
    root_logger.handlers.clear()

    # 选择 Formatter
    if log_format == "console":
        formatter = ConsoleFormatter()
    else:
        formatter = JsonFormatter()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 额外 Handler（ELK/Loki 等）
    if extra_handlers:
        for handler in extra_handlers:
            handler.setLevel(log_level)
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)

    # 配置 uvicorn 日志走统一通道
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers.clear()
    uvicorn_logger.addHandler(console_handler)
    uvicorn_logger.setLevel(log_level)

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers.clear()
    uvicorn_access_logger.addHandler(console_handler)
    uvicorn_access_logger.setLevel(log_level)

    root_logger.info(
        "日志系统初始化完成",
        extra={"level": settings.LOG_LEVEL, "format": settings.LOG_FORMAT},
    )

    return root_logger


# 全局 logger 实例
logger = logging.getLogger("app")


def get_logger(name: str) -> logging.Logger:
    """
    获取子 logger

    Args:
        name: logger 名称（通常使用模块名）

    Returns:
        子 logger 实例
    """
    return logging.getLogger(f"app.{name}")
