from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./content_ops.db"
    allowed_origins: str = "http://localhost:5173"
    upload_dir: Path = Path("uploads")
    webhook_secret: str = "development-secret"
    max_upload_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
