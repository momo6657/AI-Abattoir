"""Pokemon battle outcome prediction service.

Uses historical data, team composition, and Elo ratings
to predict battle outcomes.
"""

from __future__ import annotations

import math
from typing import Any
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonBattle, PokemonTeam
from app.models.agent import Agent


class PokemonBattlePrediction:
    """Predicts Pokemon battle outcomes based on historical data."""

    def predict_matchup(
        self,
        player1_rating: int,
        player2_rating: int,
        player1_stats: dict[str, Any] | None = None,
        player2_stats: dict[str, Any] | None = None,
        player1_team: list[dict[str, Any]] | None = None,
        player2_team: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Predict the outcome of a matchup."""
        # Base prediction from Elo ratings
        expected_p1 = 1.0 / (1.0 + math.pow(10, (player2_rating - player1_rating) / 400.0))
        expected_p2 = 1.0 - expected_p1

        # Adjust based on stats
        p1_win_rate = (player1_stats or {}).get("win_rate", 50)
        p2_win_rate = (player2_stats or {}).get("win_rate", 50)
        p1_streak = (player1_stats or {}).get("current_streak", 0)
        p2_streak = (player2_stats or {}).get("current_streak", 0)

        # Momentum adjustment
        momentum_p1 = 0
        momentum_p2 = 0
        if p1_streak > 2:
            momentum_p1 = min(5, p1_streak * 1.5)
        elif p1_streak < -2:
            momentum_p1 = max(-5, p1_streak * 1.5)
        if p2_streak > 2:
            momentum_p2 = min(5, p2_streak * 1.5)
        elif p2_streak < -2:
            momentum_p2 = max(-5, p2_streak * 1.5)

        # Team composition adjustment (simplified)
        team_adjustment = 0
        if player1_team and player2_team:
            # Count type advantages
            p1_types = set()
            p2_types = set()
            for p in player1_team:
                p1_types.update(p.get("types", []))
            for p in player2_team:
                p2_types.update(p.get("types", []))

            # Simple type count comparison
            team_adjustment = (len(p1_types) - len(p2_types)) * 0.5

        # Final prediction
        adjusted_p1 = expected_p1 + (momentum_p1 / 100) + (team_adjustment / 100)
        adjusted_p1 = max(0.05, min(0.95, adjusted_p1))
        adjusted_p2 = 1.0 - adjusted_p1

        # Confidence based on rating difference and data
        rating_diff = abs(player1_rating - player2_rating)
        confidence = "low"
        if rating_diff > 200:
            confidence = "high"
        elif rating_diff > 100:
            confidence = "medium"

        # Generate analysis
        factors = []
        if player1_rating > player2_rating:
            factors.append(f"P1 评分更高 (+{player1_rating - player2_rating})")
        elif player2_rating > player1_rating:
            factors.append(f"P2 评分更高 (+{player2_rating - player1_rating})")

        if p1_streak > 0:
            factors.append(f"P1 连胜中 ({p1_streak})")
        elif p1_streak < 0:
            factors.append(f"P1 连败中 ({abs(p1_streak)})")
        if p2_streak > 0:
            factors.append(f"P2 连胜中 ({p2_streak})")
        elif p2_streak < 0:
            factors.append(f"P2 连败中 ({abs(p2_streak)})")

        if momentum_p1 > 0:
            factors.append("P1 势头正旺")
        elif momentum_p1 < 0:
            factors.append("P1 状态低迷")

        return {
            "player1_win_probability": round(adjusted_p1 * 100, 1),
            "player2_win_probability": round(adjusted_p2 * 100, 1),
            "predicted_winner": "player1" if adjusted_p1 > 0.5 else "player2",
            "confidence": confidence,
            "factors": factors,
            "rating_difference": rating_diff,
            "base_expected": round(expected_p1 * 100, 1),
            "adjustments": {
                "momentum_p1": round(momentum_p1, 1),
                "momentum_p2": round(momentum_p2, 1),
                "team_adjustment": round(team_adjustment, 1),
            },
        }

    async def predict_battle(
        self,
        db: AsyncSession,
        player1_agent_id: uuid.UUID,
        player2_agent_id: uuid.UUID,
        player1_team_id: uuid.UUID | None = None,
        player2_team_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Predict a battle outcome between two agents."""
        # Get agents
        p1 = await db.get(Agent, player1_agent_id)
        p2 = await db.get(Agent, player2_agent_id)
        if not p1 or not p2:
            return {"error": "Both agents must exist"}

        # Get stats
        p1_stats = p1.pokemon_stats or {}
        p2_stats = p2.pokemon_stats or {}

        # Get teams if provided
        p1_team = None
        p2_team = None
        if player1_team_id:
            team1 = await db.get(PokemonTeam, player1_team_id)
            if team1:
                p1_team = team1.pokemon_list
        if player2_team_id:
            team2 = await db.get(PokemonTeam, player2_team_id)
            if team2:
                p2_team = team2.pokemon_list

        # Get historical matchup data
        historical = await self._get_historical_matchup(db, player1_agent_id, player2_agent_id)

        prediction = self.predict_matchup(
            player1_rating=p1.pokemon_rating or 1500,
            player2_rating=p2.pokemon_rating or 1500,
            player1_stats=p1_stats,
            player2_stats=p2_stats,
            player1_team=p1_team,
            player2_team=p2_team,
        )

        prediction["player1"] = {
            "agent_id": str(p1.id),
            "agent_name": p1.name,
            "rating": p1.pokemon_rating or 1500,
            "level": p1.level.value if p1.level else "novice",
        }
        prediction["player2"] = {
            "agent_id": str(p2.id),
            "agent_name": p2.name,
            "rating": p2.pokemon_rating or 1500,
            "level": p2.level.value if p2.level else "novice",
        }
        prediction["historical"] = historical

        return prediction

    async def _get_historical_matchup(
        self,
        db: AsyncSession,
        player1_id: uuid.UUID,
        player2_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get historical matchup data between two players."""
        result = await db.execute(
            select(PokemonBattle)
            .where(
                ((PokemonBattle.player1_agent_id == player1_id) & (PokemonBattle.player2_agent_id == player2_id))
                | ((PokemonBattle.player1_agent_id == player2_id) & (PokemonBattle.player2_agent_id == player1_id))
            )
            .order_by(PokemonBattle.created_at.desc())
            .limit(10)
        )
        battles = result.scalars().all()

        p1_wins = 0
        p2_wins = 0
        total_turns = 0

        for battle in battles:
            if str(battle.winner) == str(player1_id):
                p1_wins += 1
            elif str(battle.winner) == str(player2_id):
                p2_wins += 1
            total_turns += battle.turns or 0

        total = p1_wins + p2_wins
        return {
            "total_battles": len(battles),
            "player1_wins": p1_wins,
            "player2_wins": p2_wins,
            "player1_win_rate": round(p1_wins / total * 100, 1) if total else 0,
            "average_turns": round(total_turns / len(battles), 1) if battles else 0,
        }


pokemon_battle_prediction = PokemonBattlePrediction()
