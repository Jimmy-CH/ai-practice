# tests/test_config.py
"""配置模块测试"""
from app.config import Settings, BASE_DIR


def test_base_dir_is_absolute():
    """BASE_DIR 应为绝对路径"""
    assert BASE_DIR.is_absolute()


def test_base_dir_points_to_project_root():
    """BASE_DIR 应指向项目根目录（app/ 的上一级）"""
    assert (BASE_DIR / "app").is_dir()
    assert (BASE_DIR / ".env").exists()


def test_settings_defaults():
    """Settings 默认值验证"""
    s = Settings(
        _env_file=None,  # 不加载 .env，仅测试默认值
    )
    assert s.LLM_MODEL == "deepseek-chat"
    assert s.DEEPSEEK_BASE_URL == "https://api.deepseek.com"
    assert s.EMBEDDING_MODEL == "text-embedding-3-small"
    assert s.CHUNK_SIZE == 500
    assert s.CHUNK_OVERLAP == 50
    assert s.TOP_K == 5
    assert s.REDIS_HOST == "localhost"
    assert s.REDIS_PORT == 6379


def test_settings_env_file_path():
    """env_file 应指向项目根目录下的 .env"""
    s = Settings()
    expected = str(BASE_DIR / ".env")
    assert s.model_config.get("env_file") == expected
