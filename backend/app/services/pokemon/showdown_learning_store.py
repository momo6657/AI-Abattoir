"""Database-backed Pokemon Showdown learning profile store."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonShowdownBattleRecord
from app.services.pokemon.showdown_learning import ShowdownLearningProfile


class PokemonShowdownLearningStore:
    """Persists completed Showdown battle summaries and rebuilds profiles."""

    def normalize(self, username: str) -> str:
        return "".join(ch for ch in username.lower() if ch.isalnum())

    async def record_session(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        username: str,
        battle_format: str,
        showdown_format: str,
        mode: str,
        analysis: dict[str, Any],
        decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        status = str(analysis.get("status") or "in_progress")
        if status not in {"win", "loss", "tie", "finished"}:
            return await self.profile(db, username=username, battle_format=battle_format)

        existing = await self._record_by_session(db, session_id)
        if existing is None:
            record = PokemonShowdownBattleRecord(
                session_id=session_id,
                username=username,
                username_key=self.normalize(username),
                battle_format=battle_format,
                showdown_format=showdown_format,
                mode=mode,
                status=status,
                reward=float(analysis.get("reward") or 0.0),
                turns=int(analysis.get("turns") or 0),
                faints_for=int(analysis.get("faints_for") or 0),
                faints_against=int(analysis.get("faints_against") or 0),
                decisions=decisions,
                analysis=analysis,
            )
            db.add(record)
            await db.commit()
        return await self.profile(db, username=username, battle_format=battle_format)

    async def profile(self, db: AsyncSession, *, username: str, battle_format: str) -> dict[str, Any]:
        records = await self._records_for(db, username=username, battle_format=battle_format)
        if not records:
            return ShowdownLearningProfile(
                username=username,
                battle_format=battle_format,
                showdown_format=battle_format,
            ).to_dict()
        return self._build_profile(records).to_dict()

    async def list_profiles(self, db: AsyncSession) -> list[dict[str, Any]]:
        result = await db.execute(
            select(PokemonShowdownBattleRecord).order_by(PokemonShowdownBattleRecord.created_at.desc())
        )
        groups: dict[tuple[str, str], list[PokemonShowdownBattleRecord]] = {}
        for record in result.scalars().all():
            groups.setdefault((record.username_key, record.battle_format), []).append(record)
        return [self._build_profile(records).to_dict() for records in groups.values()]

    async def _record_by_session(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> PokemonShowdownBattleRecord | None:
        result = await db.execute(
            select(PokemonShowdownBattleRecord).where(PokemonShowdownBattleRecord.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def _records_for(
        self,
        db: AsyncSession,
        *,
        username: str,
        battle_format: str,
    ) -> list[PokemonShowdownBattleRecord]:
        result = await db.execute(
            select(PokemonShowdownBattleRecord)
            .where(PokemonShowdownBattleRecord.username_key == self.normalize(username))
            .where(PokemonShowdownBattleRecord.battle_format == battle_format)
            .order_by(PokemonShowdownBattleRecord.created_at.desc())
        )
        return list(result.scalars().all())

    def _build_profile(self, records: list[PokemonShowdownBattleRecord]) -> ShowdownLearningProfile:
        first = records[0]
        profile = ShowdownLearningProfile(
            username=first.username,
            battle_format=first.battle_format,
            showdown_format=first.showdown_format,
        )
        for record in records:
            profile.record(
                session_id=record.session_id,
                mode=record.mode or "balanced",
                analysis=record.analysis or {
                    "status": record.status,
                    "reward": record.reward or 0.0,
                    "turns": record.turns or 0,
                    "faints_for": record.faints_for or 0,
                    "faints_against": record.faints_against or 0,
                },
                decisions=record.decisions or [],
            )
        return profile


pokemon_showdown_learning_store = PokemonShowdownLearningStore()
