import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_missing_query(client: AsyncClient, setup_db):
    resp = await client.get("/api/search/")
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_fetch_missing_url(client: AsyncClient, setup_db):
    resp = await client.get("/api/search/fetch?url=")
    assert resp.status_code in (400, 422)
