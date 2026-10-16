"""日志配置：控制台 + 文件双输出。

- 控制台格式与既有输出保持一致
- 文件写入 backend/logs/app.log，按月轮转（app.log.2026-09），保留 12 个月
- LOG_LEVEL 环境变量控制级别，对两类输出同时生效
"""
import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class MonthlyRotatingFileHandler(TimedRotatingFileHandler):
    """按月轮转的日志文件处理器。

    每月 1 号午夜自动轮转，轮转文件命名为 app.log.2026-09。
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
        base = default_name.rsplit(".", 1)[0]  # app.log
        date_suffix = default_name.rsplit(".", 1)[1]  # YYYY-MM-DD
        return f"{base}.{date_suffix[:7]}"  # YYYY-MM

    def shouldRollover(self, record: logging.LogRecord) -> int:
        """仅在月份变化时触发轮转。"""
        if super().shouldRollover(record):
            if self.stream is None:
                self.stream = self._open()
            current_time = int(time.time())
            dst_offset = time.daylight * 3600
            time_tuple = time.localtime(current_time - dst_offset)

            if os.path.exists(self.baseFilename):
                file_time_tuple = time.localtime(os.path.getmtime(self.baseFilename))
                if time_tuple.tm_mon != file_time_tuple.tm_mon:
                    return 1
        return 0

    def getFilesToDelete(self) -> list[str]:
        """删除超出 backupCount 的旧日志文件。"""
        base_name = os.path.basename(self.baseFilename)
        dir_name = os.path.dirname(self.baseFilename)
        prefix = base_name + "."
        files = [
            os.path.join(dir_name, f)
            for f in os.listdir(dir_name)
            if f.startswith(prefix) and len(f) == len(prefix) + 7  # YYYY-MM
        ]
        files.sort()
        if len(files) <= self.backupCount:
            return []
        return files[: len(files) - self.backupCount]


def setup_logging(level: str = "INFO", log_dir: Path | str | None = None) -> None:
    """初始化日志：root logger 挂载控制台 + 按月轮转文件双 handler。

    Args:
        level: 日志级别，支持 DEBUG/INFO/WARNING/ERROR/CRITICAL。
        log_dir: 日志目录，默认 backend/logs/；测试可注入临时目录。
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    target_dir = Path(log_dir) if log_dir is not None else LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # 清除已有 handler，重复调用（测试/热重载）不得累积输出
    root_logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = MonthlyRotatingFileHandler(
        target_dir / "app.log",
        backupCount=12,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 请求访问已由 main.py 中间件记录，压掉重复的 uvicorn 访问日志
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
