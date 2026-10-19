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

    from app.prompts import spec_v1
    from app.services import llm_service

    def _module_reply() -> str:
        return _json.dumps({
            "responsibility": "负责示例模块的核心能力",
            "functions": [{"name": "示例模块功能", "logic": "读取 A 后返回 run 结果",
                          "roles": ["研发"], "priority": "P0"}],
            "flows": [{"title": "示例流程",
                       "mermaid": "flowchart TD\n A[\"开始\"] --> B[\"结束\"]"}],
            "entities": [{"name": "Sample", "table": "samples",
                          "fields": [{"name": "id", "type": "string",
                                      "constraints": "PK", "note": "主键"}],
                          "relations": []}],
            "enums": [],
            "rules": [{"topic": "读取规则", "points": ["A 必须存在"]}],
            "errorCodes": [{"scene": "读取失败", "code": "500", "ui": "提示重试"}],
            "nfr": {"performance": ["单次读取 O(1)"], "security": [],
                    "reliability": [], "deployment": [],
                    "maintainability": [], "extensibility": [], "compatibility": []},
        }, ensure_ascii=False)

    def _overview_reply() -> str:
        return _json.dumps({
            "overview": {"name": "示例项目", "positioning": "用于测试的产品说明书",
                         "problems": ["验证九节渲染"], "scope": ["仅测试环境"]},
            "roles": [{"role": "研发", "scenarios": ["查看产品说明"]}],
            "architecture": {
                "stack": [{"layer": "后端", "tech": "FastAPI", "note": "接口"}],
                "modules": [],
                "diagram": "flowchart LR\n A[\"前端\"] --> B[\"后端\"]"},
        }, ensure_ascii=False)

    async def fake_chat(system_prompt: str, user_prompt: str) -> str:
        # 步骤 3 的两次 LLM 任务共用打桩点：按系统提示词标记与用户提示前缀分流
        if spec_v1.PROMPT_MARKER in system_prompt:
            if user_prompt.startswith("模块："):
                return _module_reply()
            return _overview_reply()
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
