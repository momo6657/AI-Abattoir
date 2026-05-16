from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    mode: str = "free"
    agent_ids: List[UUID] = []
    config: dict = {}


class ConversationResponse(BaseModel):
    id: UUID
    title: Optional[str]
    mode: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    agent_id: Optional[UUID]
    role: str
    content: dict
    turn_number: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
