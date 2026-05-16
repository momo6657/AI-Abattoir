import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class MatchType(str, enum.Enum):
    QA_PK = "qa_pk"
    CODE = "code"
    CREATIVE = "creative"
    REASONING = "reasoning"
    IMAGE_GEN = "image_gen"
    VOICE = "voice"


class MatchStatus(str, enum.Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    VOTING = "voting"
    FINISHED = "finished"


class ArenaMatch(Base):
    __tablename__ = "arena_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_type = Column(Enum(MatchType), nullable=False)
    status = Column(Enum(MatchStatus), default=MatchStatus.WAITING)
    title = Column(String(200), nullable=True)
    prompt = Column(Text, nullable=False)
    config = Column(JSONB, default=dict)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    winner_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ArenaParticipant(Base):
    __tablename__ = "arena_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("arena_matches.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    response_content = Column(JSONB, nullable=True)
    vote_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ArenaVote(Base):
    __tablename__ = "arena_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("arena_matches.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("arena_participants.id", ondelete="CASCADE"), nullable=False)
    voter_session = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
