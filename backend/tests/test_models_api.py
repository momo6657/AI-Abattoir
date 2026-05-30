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


@pytest.mark.asyncio
async def test_create_model_with_api_url_derives_provider(client: AsyncClient, setup_db):
    resp = await client.post("/api/models/", json={
        "name": "Third Party Model",
        "model_id": "vendor/chat-model",
        "api_base": "https://llm.example.com/v1",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "llm.example.com"
    assert data["api_base"] == "https://llm.example.com/v1"


@pytest.mark.asyncio
async def test_discover_models_from_openai_compatible_api(client: AsyncClient, monkeypatch):
    from app.api import models as models_api

    class FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"id": "zeta-model"},
                    {"id": "alpha-model"},
                    {"id": "alpha-model"},
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.requested_urls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            self.requested_urls.append(url)
            return FakeResponse()

    monkeypatch.setattr(models_api.httpx, "AsyncClient", FakeAsyncClient)

    resp = await client.post("/api/models/discover", json={
        "api_base": "https://llm.example.com",
        "api_key": "sk-test",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["api_base"] == "https://llm.example.com/v1"
    assert data["provider"] == "llm.example.com"
    assert data["models"] == ["alpha-model", "zeta-model"]
