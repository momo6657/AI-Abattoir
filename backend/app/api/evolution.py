from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agent import EvolutionResponse, ExperienceResponse
from app.services.evolution_service import evolution_service

router = APIRouter(tags=["evolution"])


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
