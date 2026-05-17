import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.services.conversation_engine import ConversationEngine
from app.models.conversation import ConversationMode


def _make_conversation(mode: ConversationMode, agent_ids, max_turns=10):
    """Create a mock conversation with given mode and agent_ids in config."""
    conv = MagicMock()
    conv.id = uuid4()
    conv.mode = mode
    conv.config = {"agent_ids": agent_ids, "max_turns": max_turns}
    conv.title = "Test"
    return conv


def _mock_history(count):
    """Create a list of `count` mock message objects."""
    return [MagicMock(turn_number=i) for i in range(count)]


def _setup_db(db, conversation, history):
    """Configure mock db to return conversation via get() and history via execute()."""
    db.get = AsyncMock(return_value=conversation)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = history
    db.execute = AsyncMock(return_value=mock_result)
