from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.search_service import search_service

router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class FetchResult(BaseModel):
    title: str
    content: str
    url: str


@router.get("/", response_model=List[SearchResult])
async def search(query: str = Query(..., min_length=1), max_results: int = Query(5, ge=1, le=20)):
    try:
        results = await search_service.search(query, max_results)
        return results
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")


@router.get("/fetch", response_model=FetchResult)
async def fetch_url(url: str = Query(...)):
    try:
        result = await search_service.fetch_url(url)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")
