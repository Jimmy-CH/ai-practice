# app/config.py
import os

# ━━ 必须在任何 huggingface 相关模块 import 之前设置 ━━
# 使用镜像站解决 SSL 证书验证失败 / 网络不通的问题
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFICATION", "1")

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

    # 向量模型配置（本地 HuggingFace 模型，无需 API Key）
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

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
        # 忽略 .env 中未定义的多余环境变量（如已废弃的 OPENAI_API_KEY）
        extra="ignore",
    )


# 实例化全局配置单例
settings = Settings()

