from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.agent import Agent, AgentProfile
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from app.api.auth import get_current_user, get_optional_user

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent)
        .order_by(Agent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/", response_model=AgentResponse)
async def create_agent(data: AgentCreate, db: AsyncSession = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    agent = Agent(
        name=data.name,
        description=data.description,
        model_id=data.model_id,
        avatar_url=data.avatar_url,
        voice_model_id=data.voice_model_id,
    )
    db.add(agent)
    await db.flush()

    if data.profile:
        profile = AgentProfile(
            agent_id=agent.id,
            **data.profile.model_dump(),
        )
        db.add(profile)

    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: UUID, data: AgentUpdate, db: AsyncSession = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}")
async def delete_agent(agent_id: UUID, db: AsyncSession = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
    return {"detail": "Deleted"}
