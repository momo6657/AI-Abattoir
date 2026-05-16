from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List


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
