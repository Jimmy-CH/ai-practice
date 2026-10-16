import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db
from app.services.auth_service import seed_users

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await seed_users(session)
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
def isolate_pregenerate_session(db_session, monkeypatch):
    """后台预热必须复用测试会话，禁止触碰真实 materials.db。"""
    from app.api import generator as generator_module

    class _SessionCM:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(generator_module, "AsyncSessionLocal", lambda: _SessionCM())


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def editor_token(client):
    r = await client.post("/api/auth/login", data={"username": "editor", "password": "editor123"})
    return r.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def reviewer_token(client):
    r = await client.post("/api/auth/login", data={"username": "reviewer", "password": "reviewer123"})
    return r.json()["access_token"]
