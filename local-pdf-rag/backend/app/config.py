from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """运行时配置；显式声明 env_file，避免 pydantic-settings 在部分版本下不自动加载 .env。"""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBED_MODEL: str = "bge-m3"
    CHAT_MODEL: str = "qwen2.5:3b"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    TOP_K: int = 4
    MAX_UPLOAD_MB: int = 20
    OLLAMA_TIMEOUT: float = 120.0
    INDEX_PATH: str = str(BASE_DIR / "data" / "index.json")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
