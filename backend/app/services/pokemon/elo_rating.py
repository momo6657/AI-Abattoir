"""Elo rating system for Pokemon battles.

Implements the standard Elo rating algorithm with K-factor scaling
based on battle count (provisional vs established players).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.pokemon import PokemonBattle


# K-factor tiers
K_PROVISIONAL = 40      # < 30 battles
K_STANDARD = 20         # 30-100 battles
K_ESTABLISHED = 10      # > 100 battles

# Rating bounds
MIN_RATING = 100
MAX_RATING = 4000
DEFAULT_RATING = 1500

# Tier thresholds
TIERS = [
    (2200, "Grandmaster", "宗师"),
    (2000, "Master", "大师"),
    (1800, "Diamond", "钻石"),
    (1600, "Platinum", "铂金"),
    (1400, "Gold", "黄金"),
    (1200, "Silver", "白银"),
    (0, "Bronze", "青铜"),
]


@dataclass
class EloResult:
    """Result of an Elo rating calculation."""
    player1_old: int
    player1_new: int
    player1_change: int
    player2_old: int
    player2_new: int
    player2_change: int
    player1_expected: float
    player2_expected: float
    k_factor: int


class EloRatingService:
    """Calculates and manages Elo ratings for Pokemon battle agents."""

    def expected_score(self, rating_a: int, rating_b: int) -> float:
        """Calculate expected score for player A against player B."""
        return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))

    def k_factor(self, battle_count: int) -> int:
        """Determine K-factor based on battle count."""
        if battle_count < 30:
            return K_PROVISIONAL
        elif battle_count < 100:
            return K_STANDARD
        return K_ESTABLISHED

    def calculate_elo(
        self,
        rating1: int,
        rating2: int,
        score1: float,
        battle_count1: int = 50,
        battle_count2: int = 50,
    ) -> EloResult:
        """
        Calculate new Elo ratings after a battle.

        Args:
            rating1: Player 1's current rating
            rating2: Player 2's current rating
            score1: Player 1's score (1.0 = win, 0.5 = draw, 0.0 = loss)
            battle_count1: Player 1's total battles
            battle_count2: Player 2's total battles
        """
        expected1 = self.expected_score(rating1, rating2)
        expected2 = 1.0 - expected1

        # Use average K-factor for both players
        k = (self.k_factor(battle_count1) + self.k_factor(battle_count2)) // 2

        change1 = round(k * (score1 - expected1))
        change2 = round(k * ((1.0 - score1) - expected2))

        new1 = max(MIN_RATING, min(MAX_RATING, rating1 + change1))
        new2 = max(MIN_RATING, min(MAX_RATING, rating2 + change2))

        return EloResult(
            player1_old=rating1,
            player1_new=new1,
            player1_change=change1,
            player2_old=rating2,
            player2_new=new2,
            player2_change=change2,
            player1_expected=round(expected1, 4),
            player2_expected=round(expected2, 4),
            k_factor=k,
        )

    def tier_for_rating(self, rating: int) -> tuple[str, str]:
        """Return (english_name, chinese_name) tier for a rating."""
        for threshold, en, zh in TIERS:
            if rating >= threshold:
                return en, zh
        return "Bronze", "青铜"

    async def get_agent_battle_count(
        self,
        db: AsyncSession,
        agent_id: uuid.UUID,
    ) -> int:
        """Get total Pokemon battle count for an agent."""
        result = await db.execute(
            select(func.count())
            .select_from(PokemonBattle)
            .where(
                (PokemonBattle.player1_agent_id == agent_id)
                | (PokemonBattle.player2_agent_id == agent_id)
            )
        )
        return result.scalar() or 0

    async def update_ratings_after_battle(
        self,
        db: AsyncSession,
        battle: PokemonBattle,
        winner_agent_id: uuid.UUID | None,
    ) -> EloResult:
        """
        Update both players' Elo ratings after a battle.

        Args:
            battle: The completed PokemonBattle
            winner_agent_id: The winner's agent ID, or None for draw

        Returns:
            EloResult with rating changes
        """
        # Get agents
        p1 = await db.get(Agent, battle.player1_agent_id)
        p2 = await db.get(Agent, battle.player2_agent_id)
        if not p1 or not p2:
            raise ValueError("Both players must exist to update ratings")

        # Determine score
        if winner_agent_id is None:
            score1 = 0.5  # Draw
        elif winner_agent_id == p1.id:
            score1 = 1.0  # P1 wins
        else:
            score1 = 0.0  # P2 wins

        # Get battle counts
        count1 = await self.get_agent_battle_count(db, p1.id)
        count2 = await self.get_agent_battle_count(db, p2.id)

        # Calculate
        result = self.calculate_elo(
            rating1=p1.pokemon_rating or DEFAULT_RATING,
            rating2=p2.pokemon_rating or DEFAULT_RATING,
            score1=score1,
            battle_count1=count1,
            battle_count2=count2,
        )

        # Apply changes
        p1.pokemon_rating = result.player1_new
        p2.pokemon_rating = result.player2_new

        # Update battle record
        battle.rating_change_p1 = result.player1_change
        battle.rating_change_p2 = result.player2_change

        # Update pokemon_stats
        for agent, change, is_winner in [(p1, result.player1_change, score1 == 1.0), (p2, result.player2_change, score1 == 0.0)]:
            stats = agent.pokemon_stats or {}
            battles = stats.get("battles", 0) + 1
            wins = stats.get("wins", 0) + (1 if is_winner else 0)
            peak = max(stats.get("peak_rating", agent.pokemon_rating or DEFAULT_RATING), agent.pokemon_rating or DEFAULT_RATING)
            streak = stats.get("current_streak", 0)
            if is_winner:
                streak = max(0, streak) + 1
            elif score1 != 0.5:
                streak = min(0, streak) - 1
            stats.update({
                "battles": battles,
                "wins": wins,
                "losses": battles - wins,
                "win_rate": round(wins / battles * 100, 1) if battles else 0,
                "peak_rating": peak,
                "current_streak": streak,
                "best_streak": max(stats.get("best_streak", 0), streak),
                "last_rating_change": change,
            })
            agent.pokemon_stats = stats

        await db.commit()
        return result

    async def get_pokemon_leaderboard(
        self,
        db: AsyncSession,
        format_filter: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get Pokemon battle leaderboard sorted by rating."""
        query = (
            select(Agent)
            .where(Agent.pokemon_rating.isnot(None))
            .where(Agent.pokemon_rating > DEFAULT_RATING - 500)
            .order_by(Agent.pokemon_rating.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        agents = result.scalars().all()

        leaderboard = []
        for rank, agent in enumerate(agents, 1):
            stats = agent.pokemon_stats or {}
            tier_en, tier_zh = self.tier_for_rating(agent.pokemon_rating or DEFAULT_RATING)
            leaderboard.append({
                "rank": rank,
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "rating": agent.pokemon_rating or DEFAULT_RATING,
                "tier": tier_en,
                "tier_zh": tier_zh,
                "battles": stats.get("battles", 0),
                "wins": stats.get("wins", 0),
                "losses": stats.get("losses", 0),
                "win_rate": stats.get("win_rate", 0),
                "peak_rating": stats.get("peak_rating", DEFAULT_RATING),
                "current_streak": stats.get("current_streak", 0),
                "best_streak": stats.get("best_streak", 0),
                "favorite_format": agent.pokemon_favorite_format,
                "playstyle": agent.pokemon_playstyle,
                "level": agent.level.value if agent.level else "novice",
            })

        return leaderboard


elo_rating_service = EloRatingService()
