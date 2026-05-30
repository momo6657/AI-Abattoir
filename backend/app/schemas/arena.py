from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any


class ArenaMatchCreate(BaseModel):
    match_type: str
    title: Optional[str] = None
    prompt: str
    agent_ids: List[UUID] = []
    agent_a_id: Optional[UUID] = None
    agent_b_id: Optional[UUID] = None
    config: dict = {}


class ArenaMatchResponse(BaseModel):
    id: UUID
    match_type: str
    status: str
    title: Optional[str]
    prompt: str
    config: dict
    creator_id: Optional[UUID]
    winner_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    agent_a_id: Optional[UUID] = None
    agent_b_id: Optional[UUID] = None
    agent_a_name: Optional[str] = None
    agent_b_name: Optional[str] = None
    participant_a_id: Optional[UUID] = None
    participant_b_id: Optional[UUID] = None
    result_a: Optional[str] = None
    result_b: Optional[str] = None
    image_a_url: Optional[str] = None
    image_b_url: Optional[str] = None
    audio_a_url: Optional[str] = None
    audio_b_url: Optional[str] = None
    votes_a: int = 0
    votes_b: int = 0

    class Config:
        from_attributes = True


class ArenaParticipantResponse(BaseModel):
    id: UUID
    match_id: UUID
    agent_id: UUID
    agent_name: Optional[str] = None
    response_content: Optional[Any] = None
    vote_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ArenaVoteRequest(BaseModel):
    participant_id: Optional[UUID] = None
    side: Optional[str] = None
    voter_session: str = "anonymous"


class ArenaResultResponse(BaseModel):
    match: ArenaMatchResponse
    participants: List[ArenaParticipantResponse]
    total_votes: int
