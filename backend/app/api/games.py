from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.game import Game, GamePlayer
from app.schemas.game import GameCreate, GameResponse

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/", response_model=List[GameResponse])
async def list_games(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Game).order_by(Game.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=GameResponse)
async def create_game(data: GameCreate, db: AsyncSession = Depends(get_db)):
    game = Game(
        game_type=data.game_type,
        title=data.title,
        config=data.config,
    )
    db.add(game)
    await db.flush()

    for agent_id in data.agent_ids:
        player = GamePlayer(game_id=game.id, agent_id=agent_id)
        db.add(player)

    await db.commit()
    await db.refresh(game)
    return game


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(game_id: UUID, db: AsyncSession = Depends(get_db)):
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game
