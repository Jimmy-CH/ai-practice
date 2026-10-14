from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if Path(".env").exists() else None,
        env_file_encoding="utf-8",
    )
    llm_provider: str = "xingyu"  # "xingyu" | "deepseek"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"


settings = Settings()
