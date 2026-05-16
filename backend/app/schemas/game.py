from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any


class GameCreate(BaseModel):
    game_type: str
    title: Optional[str] = None
    agent_ids: List[UUID] = []
    config: dict = {}


class GameResponse(BaseModel):
    id: UUID
    game_type: str
    status: str
    title: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class GameStateResponse(BaseModel):
    game_id: str
    game_type: str
    status: str
    state: dict
    players: List[dict]
    winner_id: Optional[str] = None
    created_at: Optional[str] = None


class GameTurnResponse(BaseModel):
    round: int
    phase: str
    events: List[dict]
    game_over: bool = False
    winner: Optional[str] = None


class EndGameRequest(BaseModel):
    winner_id: Optional[UUID] = None


class HierarchyCreate(BaseModel):
    parent_agent_id: UUID
    child_agent_id: UUID
    relation_type: str = "command"
    context_id: Optional[UUID] = None


class HierarchyResponse(BaseModel):
    agent_id: str
    agent_name: str
    subordinates: List[Any] = []
