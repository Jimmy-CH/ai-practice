from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 工作区已验证：pydantic-settings v2 不显式声明 env_file 时不会读取 .env
    model_config = SettingsConfigDict(
        env_file=".env" if Path(".env").exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    xingyu_url: str = "http://10.130.13.74:8060/api/chat/chat"
    robot_code: str = "ROBOT_00000149"
    llm_provider: str = "xingyu"
    deepseek_api_key: str = ""
    llm_timeout: int = 120
    llm_max_concurrency: int = 3
    # 九节产品说明书：全量快照分模块分析的限额与并发
    spec_max_modules: int = 12
    spec_max_files_per_module: int = 12
    spec_max_file_chars: int = 4000
    spec_concurrency: int = 2
    db_url: str = "sqlite+aiosqlite:///./docrelease.db"
    archive_dir: str = "archive"
    sample_repo_dir: str = "sample_repo/order-center"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # 部署形态下前端产物目录（相对 WorkingDirectory）；目录不存在则不挂载，开发模式不受影响
    static_dir: str = "static"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
