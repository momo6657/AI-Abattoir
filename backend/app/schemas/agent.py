from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class AgentProfileCreate(BaseModel):
    persona: Optional[str] = None
    personality: Optional[str] = None
    speaking_style: Optional[str] = None
    background_story: Optional[str] = None
    strengths: List[str] = []
    system_prompt: Optional[str] = None
    custom_config: dict = {}


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    model_id: UUID
    avatar_url: Optional[str] = None
    voice_model_id: Optional[UUID] = None
    profile: Optional[AgentProfileCreate] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_id: Optional[UUID] = None
    avatar_url: Optional[str] = None
    voice_model_id: Optional[UUID] = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    model_id: UUID
    avatar_url: Optional[str]
    level: str
    experience_points: int
    created_at: datetime

    class Config:
        from_attributes = True
