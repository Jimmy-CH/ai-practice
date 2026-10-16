import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models  # noqa: F401
from app.database import Base, get_db
from app.main import app


@pytest.fixture
async def engine(tmp_path):
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_maker):
    async with session_maker() as s:
        yield s


@pytest.fixture
async def client(session_maker):
    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """默认把所有测试的 LLM 调用替换为固定 JSON，保持离线可跑；
    单个测试可用自己的 monkeypatch 覆盖（后设置的生效）。"""
    import json as _json

    from app.services import llm_service

    async def fake_chat(system_prompt: str, user_prompt: str) -> str:
        return _json.dumps({
            "features": [{"tag": "新增功能", "risk": "低", "breaking": False,
                          "title": "自动生成的功能点", "biz": "业务说明", "tech": "技术说明",
                          "visible": "无", "scope": "测试模块", "acceptance": "可验收",
                          "action": "无需操作", "role": "研发", "paths": []}],
            "highlights": [], "confidence": 0.9}, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", fake_chat)


@pytest.fixture(autouse=True)
def archive_root(session_maker, tmp_path_factory):
    """把 pipeline 的会话工厂指向测试库、归档根目录指向临时目录（每个测试隔离）。"""
    from app.services import pipeline_service

    pipeline_service.set_session_factory(session_maker)
    root = tmp_path_factory.mktemp("archive")
    pipeline_service.set_archive_root(root)
    pipeline_service._live_states.clear()
    pipeline_service._cancelled.clear()
    return root
