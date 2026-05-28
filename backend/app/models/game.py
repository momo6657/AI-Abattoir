import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class GameType(str, enum.Enum):
    WEREWOLF = "werewolf"
    DEBATE = "debate"
    CHESS = "chess"
    TEXT_ADVENTURE = "text_adventure"
    NEGOTIATION = "negotiation"


class GameStatus(str, enum.Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class Game(Base):
    __tablename__ = "games"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_type = Column(Enum(GameType), nullable=False)
    status = Column(Enum(GameStatus), default=GameStatus.WAITING)
    title = Column(String(200), nullable=True)
    config = Column(JSONB, default=dict)
    state = Column(JSONB, default=dict)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    winner_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    paused_at = Column(DateTime(timezone=True), nullable=True)


class GamePlayer(Base):
    __tablename__ = "game_players"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    role = Column(String(50), nullable=True)
    is_alive = Column(Boolean, default=True)
    config = Column(JSONB, default=dict)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
