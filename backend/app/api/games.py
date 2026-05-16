from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.game import Game, GamePlayer
from app.models.agent import Agent, AgentExperience
from app.schemas.game import (
    GameCreate, GameResponse, GameStateResponse, GameTurnResponse,
    EndGameRequest, HierarchyCreate, HierarchyResponse,
)
from app.schemas.agent import EvolutionResponse, ExperienceResponse
from app.services.game_engine import game_engine
from app.services.hierarchy_service import hierarchy_service
from app.services.evolution_service import evolution_service

router = APIRouter(tags=["games"])


@router.get("/games", response_model=List[GameResponse])
async def list_games(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Game).order_by(Game.created_at.desc()))
    return result.scalars().all()


@router.post("/games", response_model=GameResponse)
async def create_game(data: GameCreate, db: AsyncSession = Depends(get_db)):
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
async def start_game(game_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        game = await game_engine.start_game(db, game_id)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/games/{game_id}/turn", response_model=GameTurnResponse)
async def process_turn(game_id: UUID, db: AsyncSession = Depends(get_db)):
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
    game_id: UUID, data: EndGameRequest, db: AsyncSession = Depends(get_db)
):
    try:
        game = await game_engine.end_game(
            db, game_id, str(data.winner_id) if data.winner_id else None
        )
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 层级指挥系统 ==========

@router.post("/hierarchy")
async def create_hierarchy(data: HierarchyCreate, db: AsyncSession = Depends(get_db)):
    try:
        relation = await hierarchy_service.create_hierarchy(
            db, data.parent_agent_id, data.child_agent_id,
            data.relation_type, data.context_id,
        )
        return {
            "id": str(relation.id),
            "parent_agent_id": str(relation.parent_agent_id),
            "child_agent_id": str(relation.child_agent_id),
            "relation_type": relation.relation_type,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/hierarchy/{agent_id}")
async def get_hierarchy_tree(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        tree = await hierarchy_service.get_hierarchy_tree(db, agent_id)
        return tree
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== 进化系统 ==========

@router.get("/agents/{agent_id}/evolution", response_model=EvolutionResponse)
async def get_evolution(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        info = await evolution_service.calculate_level(db, agent_id)
        return info
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/agents/{agent_id}/experiences", response_model=List[ExperienceResponse])
async def get_experiences(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        log = await evolution_service.get_growth_log(db, agent_id)
        return log
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
