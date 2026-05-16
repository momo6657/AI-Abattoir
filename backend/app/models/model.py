import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Float, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class CapabilityType(str, enum.Enum):
    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    IMAGE_UNDERSTANDING = "image_understanding"
    TTS = "tts"
    STT = "stt"
    CODE_EXECUTION = "code_execution"
    VIDEO_GENERATION = "video_generation"
    SEARCH = "search"


class Model(Base):
    __tablename__ = "models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    model_id = Column(String(100), nullable=False)
    api_key = Column(String(500), nullable=True)
    api_base = Column(String(500), nullable=True)
    config = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True)
    status = Column(String(20), default="offline")
    avg_response_time = Column(Float, nullable=True)
    total_tokens_used = Column(Integer, default=0)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ModelCapability(Base):
    __tablename__ = "model_capabilities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    capability = Column(Enum(CapabilityType), nullable=False)
    config = Column(JSONB, default=dict)
