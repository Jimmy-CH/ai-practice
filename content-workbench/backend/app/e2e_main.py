import os

# 强制使用独立测试数据库
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./e2e.db")

from app.main import app
from app.api.generation import get_generator
from app.services.generation import FakeGenerator

app.dependency_overrides[get_generator] = lambda: FakeGenerator()
