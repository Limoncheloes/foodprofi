"""Shared test helpers."""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = "postgresql+asyncpg://supplyflow:supplyflow_secret@postgres:5432/supplyflow_test"


async def create_admin_headers(client: AsyncClient, phone: str, password: str = "admin123") -> dict:
    """Create an admin user directly in the DB and return auth headers.

    Uses NullPool to avoid stale asyncpg type OID cache issues when enums are
    recreated between tests.
    """
    from app.auth.jwt import hash_password
    from app.models.user import User, UserRole

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            name="Admin",
            phone=phone,
            password_hash=hash_password(password),
            role=UserRole.admin,
        )
        session.add(user)
        await session.commit()

    await engine.dispose()

    resp = await client.post("/auth/login", json={"phone": phone, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
