"""日志配置模块。

提供统一的日志格式和输出配置：
- 控制台输出（带颜色）
- 文件输出（按月轮转）
"""
import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class MonthlyRotatingFileHandler(TimedRotatingFileHandler):
    """按月轮转的日志文件处理器。

    每月 1 号午夜自动轮转，日志文件命名为 app.log.2026-09。
    """

    def __init__(self, filename, backupCount=12, encoding="utf-8"):
        super().__init__(
            filename,
            when="midnight",
            interval=1,
            backupCount=backupCount,
            encoding=encoding,
        )
        self.namer = self._month_namer

    def _month_namer(self, default_name: str) -> str:
        """将轮转文件名从 app.log.2026-09-01 改为 app.log.2026-09。"""
        # default_name 格式: app.log.YYYY-MM-DD
        base = default_name.rsplit(".", 1)[0]  # app.log
        date_suffix = default_name.rsplit(".", 1)[1]  # YYYY-MM-DD
        month_suffix = date_suffix[:7]  # YYYY-MM
        return f"{base}.{month_suffix}"

    def shouldRollover(self, record: logging.LogRecord) -> int:
        """仅在月份变化时触发轮转。"""
        # 先让父类判断是否到了午夜
        if super().shouldRollover(record):
            # 检查当前月份是否与上次轮转的月份不同
            if self.stream is None:
                self.stream = self._open()
            msg = self.format(record) + self.terminator
            current_time = int(time.time())
            dst_offset = time.daylight * 3600
            rollover_at = current_time - dst_offset
            time_tuple = time.localtime(rollover_at)

            # 读取上次轮转时间
            if os.path.exists(self.baseFilename):
                file_mtime = os.path.getmtime(self.baseFilename)
                file_time_tuple = time.localtime(file_mtime)
                if time_tuple.tm_mon != file_time_tuple.tm_mon:
                    return 1
        return 0

    def getFilesToDelete(self) -> list[str]:
        """删除超出 backupCount 的旧日志文件。"""
        base_name = os.path.basename(self.baseFilename)
        dir_name = os.path.dirname(self.baseFilename)
        prefix = base_name + "."
        files = []
        for f in os.listdir(dir_name):
            if f.startswith(prefix) and len(f) == len(prefix) + 7:  # YYYY-MM
                files.append(os.path.join(dir_name, f))
        files.sort()
        if len(files) <= self.backupCount:
            return []
        return files[: len(files) - self.backupCount]


class ColorFormatter(logging.Formatter):
    """控制台彩色日志格式化器。"""

    COLORS = {
        logging.DEBUG: "\033[36m",     # 青色
        logging.INFO: "\033[32m",      # 绿色
        logging.WARNING: "\033[33m",   # 黄色
        logging.ERROR: "\033[31m",     # 红色
        logging.CRITICAL: "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # 保存原始 levelname，上色后临时修改 record，格式化完立即还原
        # 确保不影响共享的 LogRecord 对象和其他 handler（如文件 handler）
        original_levelname = record.levelname
        color = self.COLORS.get(record.levelno, "")
        record.levelname = f"{color}{original_levelname}{self.RESET}"
        result = super().format(record)
        record.levelname = original_levelname
        return result


def setup_logging(level: str = "INFO") -> None:
    """初始化日志配置。

    Args:
        level: 日志级别，支持 DEBUG/INFO/WARNING/ERROR/CRITICAL
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有 handler，避免重复
    root_logger.handlers.clear()

    # 控制台 handler（彩色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColorFormatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # 文件 handler（按月轮转，保留 12 个月）
    file_handler = MonthlyRotatingFileHandler(
        LOG_DIR / "app.log",
        backupCount=12,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # 降低第三方库日志级别，避免刷屏
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)

    root_logger.info(f"日志系统已初始化，级别: {level.upper()}，日志目录: {LOG_DIR}")
