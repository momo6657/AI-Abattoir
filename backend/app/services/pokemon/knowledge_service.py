"""Pokemon knowledge lookup with database cache and optional web search."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonKnowledgeCache
from app.services.search_service import search_service


DEFAULT_TTL_DAYS = 7


class PokemonKnowledgeService:
    """Caches battle knowledge from local analysis or web search."""

    def __init__(self, ttl_days: int = DEFAULT_TTL_DAYS):
        self.ttl = timedelta(days=ttl_days)

    async def get_cached(
        self,
        db: AsyncSession,
        query_type: str,
        query_key: str,
    ) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(PokemonKnowledgeCache)
            .where(PokemonKnowledgeCache.query_type == query_type)
            .where(PokemonKnowledgeCache.query_key == query_key)
            .where(PokemonKnowledgeCache.expires_at > now)
            .order_by(PokemonKnowledgeCache.created_at.desc())
        )
        cached = result.scalar_one_or_none()
        return cached.content if cached else None

    async def set_cached(
        self,
        db: AsyncSession,
        query_type: str,
        query_key: str,
        content: dict[str, Any],
        source_url: str | None = None,
    ) -> PokemonKnowledgeCache:
        cache = PokemonKnowledgeCache(
            id=uuid.uuid4(),
            query_type=query_type,
            query_key=query_key,
            source_url=source_url,
            content=content,
            expires_at=datetime.now(timezone.utc) + self.ttl,
        )
        db.add(cache)
        await db.commit()
        await db.refresh(cache)
        return cache

    async def search(
        self,
        db: AsyncSession,
        query_type: str,
        query_key: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        cached = await self.get_cached(db, query_type, query_key)
        if cached:
            return {"cached": True, **cached}

        query = self._build_query(query_type, query_key)
        results = await search_service.search(query, max_results=max_results)
        content = {
            "query": query,
            "query_type": query_type,
            "query_key": query_key,
            "results": results,
        }
        source_url = results[0]["url"] if results else None
        await self.set_cached(db, query_type, query_key, content, source_url)
        return {"cached": False, **content}

    def _build_query(self, query_type: str, query_key: str) -> str:
        sources = "site:pokechamdb.com OR site:pokedb.tokyo OR site:limitlessvgc.com"
        if query_type == "species_usage":
            return f"{query_key} VGC usage moves item tera {sources}"
        if query_type == "team_analysis":
            return f"{query_key} VGC team report rental {sources}"
        if query_type == "matchup":
            return f"{query_key} Pokemon VGC matchup counterplay {sources}"
        return f"{query_key} Pokemon VGC {sources}"


pokemon_knowledge_service = PokemonKnowledgeService()
