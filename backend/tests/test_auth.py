import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register
    resp = await client.post("/auth/register", json={
        "phone": "+996700000001",
        "password": "secret123",
        "name": "Test Cook",
        "role": "cook",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data

    # Login with same credentials
    resp = await client.post("/auth/login", json={
        "phone": "+996700000001",
        "password": "secret123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "phone": "+996700000002",
        "password": "correct",
        "name": "User",
        "role": "cook",
    })
    resp = await client.post("/auth/login", json={
        "phone": "+996700000002",
        "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_phone_rejected(client: AsyncClient):
    payload = {"phone": "+996700000003", "password": "pass", "name": "A", "role": "cook"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "phone": "+996700000004",
        "password": "pass",
        "name": "B",
        "role": "buyer",
    })
    refresh = resp.json()["refresh_token"]
    resp2 = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp2.status_code == 200
    assert "access_token" in resp2.json()
