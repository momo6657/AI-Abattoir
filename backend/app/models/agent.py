import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class AgentLevel(str, enum.Enum):
    NOVICE = "novice"
    PROFICIENT = "proficient"
    EXPERT = "expert"
    MASTER = "master"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    voice_model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=True)
    is_template = Column(String(1), default="0")
    level = Column(Enum(AgentLevel), default=AgentLevel.NOVICE)
    experience_points = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, unique=True)
    persona = Column(Text, nullable=True)
    personality = Column(Text, nullable=True)
    speaking_style = Column(Text, nullable=True)
    background_story = Column(Text, nullable=True)
    strengths = Column(JSONB, default=list)
    system_prompt = Column(Text, nullable=True)
    custom_config = Column(JSONB, default=dict)


class AgentHierarchy(Base):
    __tablename__ = "agent_hierarchy"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    child_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(50), default="command")
    context_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AgentExperience(Base):
    __tablename__ = "agent_experiences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_type = Column(String(50), nullable=False)
    context_id = Column(UUID(as_uuid=True), nullable=True)
    decision = Column(Text, nullable=True)
    outcome = Column(Text, nullable=True)
    lesson = Column(Text, nullable=True)
    xp_gained = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
