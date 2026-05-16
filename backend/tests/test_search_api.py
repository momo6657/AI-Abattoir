import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_missing_query(client: AsyncClient):
    resp = await client.get("/api/search")
    assert resp.status_code == 422  # missing required query param


@pytest.mark.asyncio
async def test_fetch_missing_url(client: AsyncClient):
    resp = await client.get("/api/search/fetch")
    assert resp.status_code == 422
