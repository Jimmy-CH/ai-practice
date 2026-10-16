"""应用装配入口：日志初始化 → 中间件 → CORS → 路由 → 静态托管。

具体实现分域存放：
- 请求日志中间件：app/middleware/request_log.py
- 建表/迁移/种子（lifespan）：app/db_bootstrap.py
- 静态托管与 SPA 回退：app/static_serving.py
- 接口路由集中注册：app/api/router.py
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import register_routers
from app.config import settings
from app.db_bootstrap import lifespan
from app.logging_config import setup_logging
from app.middleware.request_log import register_request_log_middleware
from app.static_serving import register_static


logger = logging.getLogger("app.main")
# 控制台 + 按月轮转文件双输出，级别由 LOG_LEVEL 控制
setup_logging(settings.log_level)


app = FastAPI(title="AI 运营物料智能生成助手", lifespan=lifespan)
register_request_log_middleware(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# 全部接口路由集中在 app/api/router.py 注册，便于一文件总览所有接口
register_routers(app)
# 静态托管必须在所有 API 路由注册之后调用，避免 SPA catch-all 拦截 /api
register_static(app, Path(settings.static_dir))
