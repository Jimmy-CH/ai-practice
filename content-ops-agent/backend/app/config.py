from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./content_ops.db"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: Path = Path("uploads")
    webhook_secret: str = "development-secret"
    max_upload_bytes: int = 10 * 1024 * 1024
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    max_evidence_chunks: int = 6

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
