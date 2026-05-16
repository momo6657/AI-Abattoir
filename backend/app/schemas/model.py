from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ModelCreate(BaseModel):
    name: str
    provider: str
    model_id: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    config: dict = {}


class ModelUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None


class ModelResponse(BaseModel):
    id: UUID
    name: str
    provider: str
    model_id: str
    is_active: bool
    status: str
    avg_response_time: Optional[float]
    total_tokens_used: int
    created_at: datetime

    class Config:
        from_attributes = True
