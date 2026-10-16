"""日志配置：控制台 + 按月轮转文件双输出。"""
import logging

import pytest

from app.logging_config import setup_logging


@pytest.fixture
def isolated_root_logger():
    """还原 root logger 状态，避免测试间 handler/级别串扰。"""
    root = logging.getLogger()
    saved_level = root.level
    saved_handlers = list(root.handlers)
    noisy = ("uvicorn.access", "sqlalchemy.engine")
    saved_noisy = {name: logging.getLogger(name).level for name in noisy}
    yield root
    root.setLevel(saved_level)
    root.handlers.clear()
    root.handlers.extend(saved_handlers)
    for name, level in saved_noisy.items():
        logging.getLogger(name).setLevel(level)


def _flush(root: logging.Logger) -> None:
    for handler in root.handlers:
        handler.flush()


def test_setup_logging_writes_to_file(isolated_root_logger, tmp_path):
    """核心需求：日志内容必须写入 app.log 文件，且格式带 logger 名。"""
    setup_logging("INFO", log_dir=tmp_path)
    logging.getLogger("app.test").info("hello-file")
    _flush(isolated_root_logger)
    content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "hello-file" in content
    assert "app.test" in content


def test_setup_logging_keeps_console_output(isolated_root_logger, tmp_path):
    """控制台输出保留：root 上必须同时挂 StreamHandler 与 FileHandler。"""
    setup_logging("INFO", log_dir=tmp_path)
    handlers = isolated_root_logger.handlers
    assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in handlers)
    assert any(isinstance(h, logging.FileHandler) for h in handlers)


def test_setup_logging_level_filters_file(isolated_root_logger, tmp_path):
    """LOG_LEVEL 过滤对文件输出同样生效。"""
    setup_logging("WARNING", log_dir=tmp_path)
    logging.getLogger("app.test").info("should-not-appear")
    logging.getLogger("app.test").warning("should-appear")
    _flush(isolated_root_logger)
    content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "should-not-appear" not in content
    assert "should-appear" in content


def test_setup_logging_idempotent(isolated_root_logger, tmp_path):
    """重复调用不得累积 handler（main.py 顶层调用 + 测试/热重载场景）。"""
    setup_logging("INFO", log_dir=tmp_path)
    first_count = len(isolated_root_logger.handlers)
    setup_logging("INFO", log_dir=tmp_path)
    assert len(isolated_root_logger.handlers) == first_count


def test_setup_logging_creates_log_dir(tmp_path):
    """日志目录不存在时自动创建（首次部署/新环境）。"""
    log_dir = tmp_path / "nested" / "logs"
    root = logging.getLogger()
    saved_level = root.level
    saved_handlers = list(root.handlers)
    try:
        setup_logging("INFO", log_dir=log_dir)
        logging.getLogger("app.test").info("dir-created")
        _flush(root)
        assert (log_dir / "app.log").exists()
        assert "dir-created" in (log_dir / "app.log").read_text(encoding="utf-8")
    finally:
        root.setLevel(saved_level)
        root.handlers.clear()
        root.handlers.extend(saved_handlers)
