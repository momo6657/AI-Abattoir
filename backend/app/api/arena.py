from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.arena import ArenaMatch, ArenaParticipant, MatchType
from app.models.agent import Agent
from app.schemas.arena import (
    ArenaMatchCreate, ArenaMatchResponse, ArenaParticipantResponse,
    ArenaVoteRequest, ArenaResultResponse,
)
from app.services.arena_engine import arena_engine

router = APIRouter(tags=["arena"])


@router.post("/arena/matches", response_model=ArenaMatchResponse)
async def create_match(data: ArenaMatchCreate, db: AsyncSession = Depends(get_db)):
    # Validate match_type
    valid_types = {t.value for t in MatchType}
    if data.match_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid match_type '{data.match_type}'. Must be one of: {', '.join(sorted(valid_types))}")

    # Validate at least 2 agents
    if len(data.agent_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 agents are required for a match")

    # For voice type, ensure TTS config is provided
    if data.match_type == MatchType.VOICE.value:
        if not data.config.get("tts_config"):
            raise HTTPException(status_code=400, detail="Voice matches require 'tts_config' in config")

    try:
        match = await arena_engine.create_match(
            db,
            match_type=data.match_type,
            prompt=data.prompt,
            agent_ids=[str(a) for a in data.agent_ids],
            config=data.config,
            title=data.title,
        )
        return match
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/arena/matches", response_model=List[ArenaMatchResponse])
async def list_matches(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ArenaMatch)
        .order_by(ArenaMatch.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/arena/matches/{match_id}")
async def get_match(match_id: UUID, db: AsyncSession = Depends(get_db)):
    match = await db.get(ArenaMatch, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    result = await db.execute(
        select(ArenaParticipant).where(ArenaParticipant.match_id == match.id)
    )
    participants = result.scalars().all()

    participant_list = []
    for p in participants:
        agent = await db.get(Agent, p.agent_id)
        participant_list.append({
            "id": str(p.id),
            "match_id": str(p.match_id),
            "agent_id": str(p.agent_id),
            "agent_name": agent.name if agent else "Unknown",
            "response_content": p.response_content,
            "vote_count": p.vote_count or 0,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return {
        "match": {
            "id": str(match.id),
            "match_type": match.match_type,
            "status": match.status,
            "title": match.title,
            "prompt": match.prompt,
            "config": match.config,
            "creator_id": str(match.creator_id) if match.creator_id else None,
            "winner_id": str(match.winner_id) if match.winner_id else None,
            "created_at": match.created_at.isoformat() if match.created_at else None,
            "updated_at": match.updated_at.isoformat() if match.updated_at else None,
        },
        "participants": participant_list,
    }


@router.post("/arena/matches/{match_id}/start", response_model=ArenaMatchResponse)
async def start_match(match_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        match = await arena_engine.start_match(db, str(match_id))
        return match
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/arena/matches/{match_id}/vote")
async def vote(match_id: UUID, data: ArenaVoteRequest, db: AsyncSession = Depends(get_db)):
    try:
        vote_obj = await arena_engine.vote(
            db,
            match_id=str(match_id),
            participant_id=str(data.participant_id),
            voter_session=data.voter_session,
        )
        return {
            "id": str(vote_obj.id),
            "match_id": str(vote_obj.match_id),
            "participant_id": str(vote_obj.participant_id),
            "voter_session": vote_obj.voter_session,
            "created_at": vote_obj.created_at.isoformat() if vote_obj.created_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/arena/matches/{match_id}/results")
async def get_results(match_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        results = await arena_engine.get_results(db, str(match_id))
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/arena/matches/{match_id}/finish")
async def finish_match(match_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        results = await arena_engine.finish_match(db, str(match_id))
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
