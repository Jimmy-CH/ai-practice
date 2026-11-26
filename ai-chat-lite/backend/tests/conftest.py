import os
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="ai-chat-lite-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_TMP_DIR) / 'test.db'}"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import Base, engine
from app.main import app
from app.services import stream_manager as stream_manager_module


@pytest.fixture(autouse=True)
async def clean_db():
    await stream_manager_module.manager.ashutdown()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await stream_manager_module.manager.ashutdown()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
