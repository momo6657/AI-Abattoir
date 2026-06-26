"""Pokemon battle statistics tracking service.

Tracks comprehensive battle statistics for agents, formats,
and Pokemon species usage/performance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonBattle, PokemonDecision, PokemonTeam
from app.models.agent import Agent


class PokemonStatsTracker:
    """Tracks and aggregates Pokemon battle statistics."""

    async def get_agent_stats(
        self,
        db: AsyncSession,
        agent_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get comprehensive stats for an agent."""
        agent = await db.get(Agent, agent_id)
        if not agent:
            return {"error": "Agent not found"}

        rating = agent.pokemon_rating or 1500
        stats = agent.pokemon_stats or {}

        # Get battle count
        battle_count = await db.execute(
            select(func.count())
            .select_from(PokemonBattle)
            .where(
                (PokemonBattle.player1_agent_id == agent_id)
                | (PokemonBattle.player2_agent_id == agent_id)
            )
        )
        total_battles = battle_count.scalar() or 0

        # Get win count
        win_count = await db.execute(
            select(func.count())
            .select_from(PokemonBattle)
            .where(PokemonBattle.winner == str(agent_id))
        )
        wins = win_count.scalar() or 0

        # Get average turns
        avg_turns = await db.execute(
            select(func.avg(PokemonBattle.turns))
            .where(
                (PokemonBattle.player1_agent_id == agent_id)
                | (PokemonBattle.player2_agent_id == agent_id)
            )
        )
        average_turns = avg_turns.scalar() or 0

        # Get decision count
        decision_count = await db.execute(
            select(func.count())
            .select_from(PokemonDecision)
            .where(PokemonDecision.agent_id == agent_id)
        )
        total_decisions = decision_count.scalar() or 0

        # Get average confidence
        avg_confidence = await db.execute(
            select(func.avg(PokemonDecision.confidence))
            .where(PokemonDecision.agent_id == agent_id)
        )
        average_confidence = avg_confidence.scalar() or 0

        # Get recent battles
        recent = await db.execute(
            select(PokemonBattle)
            .where(
                (PokemonBattle.player1_agent_id == agent_id)
                | (PokemonBattle.player2_agent_id == agent_id)
            )
            .order_by(PokemonBattle.created_at.desc())
            .limit(5)
        )
        recent_battles = [
            {
                "id": str(b.id),
                "format": b.battle_format,
                "turns": b.turns,
                "winner": str(b.winner) if b.winner else None,
                "won": str(b.winner) == str(agent_id),
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in recent.scalars().all()
        ]

        # Get favorite format
        format_count = await db.execute(
            select(PokemonBattle.battle_format, func.count())
            .where(
                (PokemonBattle.player1_agent_id == agent_id)
                | (PokemonBattle.player2_agent_id == agent_id)
            )
            .group_by(PokemonBattle.battle_format)
            .order_by(func.count().desc())
            .limit(1)
        )
        format_row = format_count.first()
        favorite_format = format_row[0] if format_row else None

        from app.services.pokemon.elo_rating import elo_rating_service
        tier_en, tier_zh = elo_rating_service.tier_for_rating(rating)

        return {
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "rating": rating,
            "tier": tier_en,
            "tier_zh": tier_zh,
            "level": agent.level.value if agent.level else "novice",
            "playstyle": agent.pokemon_playstyle,
            "favorite_format": favorite_format or agent.pokemon_favorite_format,
            "total_battles": total_battles,
            "wins": wins,
            "losses": total_battles - wins,
            "win_rate": round(wins / total_battles * 100, 1) if total_battles else 0,
            "average_turns": round(average_turns, 1),
            "total_decisions": total_decisions,
            "average_confidence": round(average_confidence, 3) if average_confidence else 0,
            "peak_rating": stats.get("peak_rating", rating),
            "current_streak": stats.get("current_streak", 0),
            "best_streak": stats.get("best_streak", 0),
            "recent_battles": recent_battles,
        }

    async def get_format_stats(
        self,
        db: AsyncSession,
        battle_format: str,
    ) -> dict[str, Any]:
        """Get stats for a specific battle format."""
        # Total battles in this format
        total = await db.execute(
            select(func.count())
            .select_from(PokemonBattle)
            .where(PokemonBattle.battle_format == battle_format)
        )
        total_battles = total.scalar() or 0

        # Average turns
        avg_turns = await db.execute(
            select(func.avg(PokemonBattle.turns))
            .where(PokemonBattle.battle_format == battle_format)
        )
        average_turns = avg_turns.scalar() or 0

        # Most active agents
        active = await db.execute(
            select(PokemonBattle.player1_agent_id, func.count())
            .where(PokemonBattle.battle_format == battle_format)
            .group_by(PokemonBattle.player1_agent_id)
            .order_by(func.count().desc())
            .limit(5)
        )
        most_active = [
            {"agent_id": str(row[0]), "battles": row[1]}
            for row in active.all()
        ]

        return {
            "format": battle_format,
            "total_battles": total_battles,
            "average_turns": round(average_turns, 1),
            "most_active_agents": most_active,
        }

    async def get_global_stats(self, db: AsyncSession) -> dict[str, Any]:
        """Get global Pokemon battle statistics."""
        # Total battles
        total = await db.execute(select(func.count()).select_from(PokemonBattle))
        total_battles = total.scalar() or 0

        # Total agents with ratings
        agents = await db.execute(
            select(func.count())
            .select_from(Agent)
            .where(Agent.pokemon_rating.isnot(None))
        )
        total_agents = agents.scalar() or 0

        # Total decisions
        decisions = await db.execute(select(func.count()).select_from(PokemonDecision))
        total_decisions = decisions.scalar() or 0

        # Average rating
        avg_rating = await db.execute(
            select(func.avg(Agent.pokemon_rating))
            .where(Agent.pokemon_rating.isnot(None))
        )
        average_rating = avg_rating.scalar() or 1500

        # Format distribution
        format_dist = await db.execute(
            select(PokemonBattle.battle_format, func.count())
            .group_by(PokemonBattle.battle_format)
            .order_by(func.count().desc())
        )
        format_distribution = [
            {"format": row[0], "battles": row[1]}
            for row in format_dist.all()
        ]

        return {
            "total_battles": total_battles,
            "total_agents": total_agents,
            "total_decisions": total_decisions,
            "average_rating": round(average_rating),
            "format_distribution": format_distribution,
        }


pokemon_stats_tracker = PokemonStatsTracker()
