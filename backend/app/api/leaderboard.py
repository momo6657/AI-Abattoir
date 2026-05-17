from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.agent import Agent, AgentExperience
from app.models.game import Game, GamePlayer

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/")
async def get_leaderboard(
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get agent leaderboard with stats."""
    # Get all agents with their experience
    result = await db.execute(
        select(Agent).order_by(Agent.experience_points.desc())
    )
    agents = result.scalars().all()

    leaderboard = []
    for rank, agent in enumerate(agents, 1):
        # Count games played
        games_result = await db.execute(
            select(func.count())
            .select_from(GamePlayer)
            .where(GamePlayer.agent_id == agent.id)
        )
        games_played = games_result.scalar() or 0

        # Count games won
        wins_result = await db.execute(
            select(func.count())
            .select_from(Game)
            .where(Game.winner_id == agent.id)
        )
        wins = wins_result.scalar() or 0

        # Calculate win rate
        win_rate = (wins / games_played * 100) if games_played > 0 else 0

        # Get experience count
        exp_result = await db.execute(
            select(func.count())
            .select_from(AgentExperience)
            .where(AgentExperience.agent_id == agent.id)
        )
        experience_count = exp_result.scalar() or 0

        leaderboard.append({
            "rank": rank,
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "level": agent.level.value if agent.level else "novice",
            "experience_points": agent.experience_points or 0,
            "games_played": games_played,
            "wins": wins,
            "losses": games_played - wins,
            "win_rate": round(win_rate, 1),
            "experience_count": experience_count,
        })

    return leaderboard
