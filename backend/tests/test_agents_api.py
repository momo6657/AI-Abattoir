import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_agents_empty(client: AsyncClient):
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_agent_unauthorized(client: AsyncClient):
    resp = await client.post("/api/agents", json={
        "name": "Test Agent",
        "model_id": "00000000-0000-0000-0000-000000000000",
    })
    assert resp.status_code in (401, 403)
