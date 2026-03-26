import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_session
from app.main import app
from helpers import TEST_DATABASE_URL

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True, scope="function")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async def override_get_session():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> dict:
    """Create admin user directly in DB (bypasses self-registration restriction)."""
    from app.auth.jwt import hash_password
    from app.models.user import User, UserRole

    async with TestSession() as session:
        user = User(
            name="TestAdmin",
            phone="+99699000001",
            password_hash=hash_password("admin123"),
            role=UserRole.admin,
        )
        session.add(user)
        await session.commit()

    resp = await client.post(
        "/auth/login", json={"phone": "+99699000001", "password": "admin123"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
