from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any


class ArenaMatchCreate(BaseModel):
    match_type: str
    title: Optional[str] = None
    prompt: str
    agent_ids: List[UUID]
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
    participant_id: UUID
    voter_session: str


class ArenaResultResponse(BaseModel):
    match: ArenaMatchResponse
    participants: List[ArenaParticipantResponse]
    total_votes: int
