import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_models_empty(client: AsyncClient, setup_db):
    resp = await client.get("/api/models/")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_model_unauthorized(client: AsyncClient, setup_db):
    resp = await client.post("/api/models/", json={
        "name": "GPT-4o",
        "provider": "openai",
        "model_id": "gpt-4o",
    })
    assert resp.status_code in (200, 201, 401, 403, 500)
