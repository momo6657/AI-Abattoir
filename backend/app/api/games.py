from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.game import Game, GamePlayer, GameType
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.game import (
    GameCreate, GameResponse, GameStateResponse, GameTurnResponse,
    EndGameRequest,
)
from app.services.game_engine import game_engine

router = APIRouter(tags=["games"])


@router.get("/games", response_model=List[GameResponse])
async def list_games(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Game)
        .order_by(Game.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/games", response_model=GameResponse)
async def create_game(data: GameCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Validate game_type
    valid_types = {t.value for t in GameType}
    if data.game_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid game_type '{data.game_type}'. Must be one of: {', '.join(sorted(valid_types))}")

    # Validate agent count per game type
    num_agents = len(data.agent_ids)
    game_type = data.game_type
    if game_type == GameType.WEREWOLF.value:
        if num_agents < 4 or num_agents > 12:
            raise HTTPException(status_code=400, detail="Werewolf requires 4-12 agents")
    elif game_type == GameType.DEBATE.value:
        if num_agents < 2 or num_agents > 3:
            raise HTTPException(status_code=400, detail="Debate requires 2-3 agents")
    elif game_type == GameType.CHESS.value:
        if num_agents != 2:
            raise HTTPException(status_code=400, detail="Chess requires exactly 2 agents")
    elif game_type == GameType.TEXT_ADVENTURE.value:
        if num_agents < 2 or num_agents > 6:
            raise HTTPException(status_code=400, detail="Text adventure requires 2-6 agents")
    elif game_type == GameType.NEGOTIATION.value:
        if num_agents < 2:
            raise HTTPException(status_code=400, detail="Negotiation requires at least 2 agents")

    game = await game_engine.create_game(
        db, data.game_type, data.config, [str(a) for a in data.agent_ids]
    )
    return game


@router.get("/games/{game_id}", response_model=GameResponse)
async def get_game(game_id: UUID, db: AsyncSession = Depends(get_db)):
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.post("/games/{game_id}/start", response_model=GameResponse)
async def start_game(game_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        game = await game_engine.start_game(db, game_id)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/games/{game_id}/turn", response_model=GameTurnResponse)
async def process_turn(game_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        result = await game_engine.process_turn(db, game_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/games/{game_id}/state", response_model=GameStateResponse)
async def get_game_state(game_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        state = await game_engine.get_game_state(db, game_id)
        return state
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/games/{game_id}/end", response_model=GameResponse)
async def end_game(
    game_id: UUID, data: EndGameRequest, db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        game = await game_engine.end_game(
            db, game_id, str(data.winner_id) if data.winner_id else None
        )
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
