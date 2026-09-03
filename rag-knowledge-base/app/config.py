# app/config.py
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（app/ 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ================= LLM 配置 =================
    # DeepSeek API Key，从环境变量 DEEPSEEK_API_KEY 读取
    DEEPSEEK_API_KEY: str = "your-api-key-here"

    # DeepSeek 官方兼容接口地址
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # 对话模型配置
    LLM_MODEL: str = "deepseek-chat"

    # 向量模型配置 (DeepSeek 目前主要提供对话模型，Embedding 建议仍使用 OpenAI 或本地 BGE 模型)
    # 若需完全本地化，可替换为本地 Embedding 模型配置
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_API_KEY: str = "your-openai-key-here"  # 仅用于 Embedding

    # ================= 向量数据库配置 =================
    VECTOR_DB_PATH: str = "./chroma_db"

    # ================= 业务配置 =================
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5

    # ================= Redis 缓存配置 =================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    model_config = SettingsConfigDict(
        # 指定环境变量文件路径
        env_file=str(BASE_DIR / ".env"),
        # 允许字段名大小写不敏感匹配环境变量
        case_sensitive=False,
    )


# 实例化全局配置单例
settings = Settings()

