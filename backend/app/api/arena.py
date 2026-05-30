from uuid import UUID
from typing import List
import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["arena"])


MATCH_TYPE_ALIASES = {
    "qa": MatchType.QA_PK.value,
    "image": MatchType.IMAGE_GEN.value,
}


def _normalize_match_type(match_type: str) -> str:
    return MATCH_TYPE_ALIASES.get(match_type, match_type)


def _content_text(content) -> str | None:
    if content is None:
        return None
    if isinstance(content, dict):
        if content.get("error"):
            return f"生成失败：{content['error']}"
        return content.get("content") or content.get("text") or content.get("prompt_used")
    return str(content)


def _image_url(content) -> str | None:
    if not isinstance(content, dict):
        return None
    if content.get("image_url"):
        return content["image_url"]
    if content.get("image_b64"):
        return f"data:image/png;base64,{content['image_b64']}"
    return None


def _audio_url(content) -> str | None:
    if not isinstance(content, dict):
        return None
    if content.get("audio_url"):
        return content["audio_url"]
    if content.get("audio_b64"):
        return f"data:audio/mpeg;base64,{content['audio_b64']}"
    return None


async def _enrich_match(db: AsyncSession, match: ArenaMatch) -> dict:
    result = await db.execute(
        select(ArenaParticipant)
        .where(ArenaParticipant.match_id == match.id)
        .order_by(ArenaParticipant.created_at.asc())
    )
    participants = result.scalars().all()

    enriched = {
        "id": match.id,
        "match_type": match.match_type.value if hasattr(match.match_type, "value") else match.match_type,
        "status": match.status.value if hasattr(match.status, "value") else match.status,
        "title": match.title,
        "prompt": match.prompt,
        "config": match.config or {},
        "creator_id": match.creator_id,
        "winner_id": match.winner_id,
        "created_at": match.created_at,
        "updated_at": match.updated_at,
        "votes_a": 0,
        "votes_b": 0,
    }

    slots = ("a", "b")
    for index, participant in enumerate(participants[:2]):
        slot = slots[index]
        agent = await db.get(Agent, participant.agent_id)
        content = participant.response_content
        enriched[f"participant_{slot}_id"] = participant.id
        enriched[f"agent_{slot}_id"] = participant.agent_id
        enriched[f"agent_{slot}_name"] = agent.name if agent else "Unknown"
        enriched[f"result_{slot}"] = _content_text(content)
        enriched[f"image_{slot}_url"] = _image_url(content)
        enriched[f"audio_{slot}_url"] = _audio_url(content)
        enriched[f"votes_{slot}"] = participant.vote_count or 0

    return enriched


@router.post("/arena/matches", response_model=ArenaMatchResponse)
async def create_match(data: ArenaMatchCreate, db: AsyncSession = Depends(get_db)):
    match_type = _normalize_match_type(data.match_type)
    agent_ids = list(data.agent_ids)
    if not agent_ids and data.agent_a_id and data.agent_b_id:
        agent_ids = [data.agent_a_id, data.agent_b_id]

    # Validate match_type
    valid_types = {t.value for t in MatchType}
    if match_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid match_type '{data.match_type}'. Must be one of: {', '.join(sorted(valid_types))}")

    # Validate at least 2 agents
    if len(agent_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 agents are required for a match")

    # For voice type, ensure TTS config is provided
    if match_type == MatchType.VOICE.value:
        if not data.config.get("tts_config"):
            raise HTTPException(status_code=400, detail="Voice matches require 'tts_config' in config")

    # For image_gen type, validate config if provided
    if match_type == MatchType.IMAGE_GEN.value:
        image_provider = data.config.get("image_provider", "openai")
        supported_providers = {"openai", "stability"}
        if image_provider not in supported_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image_provider '{image_provider}'. Must be one of: {', '.join(sorted(supported_providers))}",
            )

    try:
        match = await arena_engine.create_match(
            db,
            match_type=match_type,
            prompt=data.prompt,
            agent_ids=[str(a) for a in agent_ids],
            config=data.config,
            title=data.title,
        )
        return await _enrich_match(db, match)
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
    matches = result.scalars().all()
    return [await _enrich_match(db, match) for match in matches]


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
        return await _enrich_match(db, match)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/arena/matches/{match_id}/vote")
async def vote(match_id: UUID, data: ArenaVoteRequest, db: AsyncSession = Depends(get_db)):
    try:
        participant_id = data.participant_id
        if participant_id is None and data.side in {"a", "b"}:
            result = await db.execute(
                select(ArenaParticipant)
                .where(ArenaParticipant.match_id == match_id)
                .order_by(ArenaParticipant.created_at.asc())
            )
            participants = result.scalars().all()
            index = 0 if data.side == "a" else 1
            if len(participants) <= index:
                raise ValueError("Participant not found for selected side")
            participant_id = participants[index].id
        if participant_id is None:
            raise ValueError("participant_id or side is required")

        vote_obj = await arena_engine.vote(
            db,
            match_id=str(match_id),
            participant_id=str(participant_id),
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
