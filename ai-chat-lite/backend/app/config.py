import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

# 默认库文件固定在 backend/ 下，避免受启动目录影响。
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{(BASE_DIR / 'lite.db').as_posix()}"


class Settings:
    PROJECT_NAME: str = "AI Chat Lite"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    MAX_CONTEXT_MESSAGES: int = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))
    STREAM_TIMEOUT_SECONDS: int = int(os.getenv("STREAM_TIMEOUT_SECONDS", "120"))
    HEARTBEAT_SECONDS: float = float(os.getenv("HEARTBEAT_SECONDS", "15"))
    FLUSH_INTERVAL_SECONDS: float = float(os.getenv("FLUSH_INTERVAL_SECONDS", "0.5"))
    SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", "你是一个乐于助人的中文助手。")
    FRONTEND_DIR: Path = BASE_DIR.parent / "frontend"


settings = Settings()
