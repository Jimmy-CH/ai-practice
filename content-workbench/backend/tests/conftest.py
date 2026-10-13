import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.content import User


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with session_factory() as session:
        session.add_all([
            User(username="editor", password_hash=hash_password("editor123"), role="editor"),
            User(username="reviewer", password_hash=hash_password("review123"), role="reviewer"),
        ])
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def editor_headers(client) -> dict:
    response = await client.post("/api/auth/login", json={"username": "editor", "password": "editor123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest_asyncio.fixture
async def reviewer_headers(client) -> dict:
    response = await client.post("/api/auth/login", json={"username": "reviewer", "password": "review123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}
