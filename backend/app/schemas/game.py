from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any

from app.models.game import GameType, GameStatus


class GameCreate(BaseModel):
    game_type: GameType
    title: str
    agent_ids: list[UUID] = []
    config: dict = {}
    max_turns: int = 20


class GameResponse(BaseModel):
    id: str
    game_type: GameType
    title: str
    status: GameStatus
    config: dict = {}
    players: list[dict] = []
    current_turn: int = 0
    max_turns: int = 20
    winner_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GameStateResponse(BaseModel):
    game_id: str
    game_type: str
    status: str
    state: dict
    players: List[dict]
    events: List[dict] = []
    winner_id: Optional[str] = None
    winner: Optional[str] = None
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
