import pytest
from uuid import uuid4

from app.services.conversation_engine import ConversationEngine
from app.models.conversation import ConversationMode


def _make_conversation(mode: ConversationMode, agent_ids, max_turns=10):
    """Create a mock conversation with given mode and agent_ids in config."""
    conv = type("Conversation", (), {
        "id": uuid4(),
        "mode": mode,
        "config": {"agent_ids": agent_ids, "max_turns": max_turns},
        "title": "Test",
    })()
    return conv


def _mock_history(count):
    """Create a list of `count` mock message objects."""
    return [type("Message", (), {"turn_number": i})() for i in range(count)]


@pytest.mark.asyncio
async def test_free_mode_rotation():
    """In free mode, agents rotate in order: 0, 1, 2, 0, 1, 2, ..."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4(), uuid4()]
    conv = _make_conversation(ConversationMode.FREE, agent_ids)

    from unittest.mock import AsyncMock, MagicMock
    db = AsyncMock()

    for turn in range(6):
        history = _mock_history(turn)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = history
        db.execute.return_value = mock_result

        next_agent = await engine.get_next_agent(db, conv.id)
        expected = agent_ids[turn % 3]
        assert next_agent == expected, (
            f"Turn {turn}: expected agent {turn % 3}, got different agent"
        )


@pytest.mark.asyncio
async def test_debate_mode_sides():
    """In debate mode, agents alternate: 0, 1, 0, 1, ..."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4()]
    conv = _make_conversation(ConversationMode.DEBATE, agent_ids)

    from unittest.mock import AsyncMock, MagicMock
    db = AsyncMock()

    for turn in range(6):
        history = _mock_history(turn)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = history
        db.execute.return_value = mock_result

        next_agent = await engine.get_next_agent(db, conv.id)
        expected = agent_ids[turn % 2]
        assert next_agent == expected


@pytest.mark.asyncio
async def test_relay_mode_sequence():
    """In relay mode, agents rotate in order: 0, 1, 2, 0, 1, 2, ..."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4(), uuid4()]
    conv = _make_conversation(ConversationMode.RELAY, agent_ids)

    from unittest.mock import AsyncMock, MagicMock
    db = AsyncMock()

    for turn in range(6):
        history = _mock_history(turn)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = history
        db.execute.return_value = mock_result

        next_agent = await engine.get_next_agent(db, conv.id)
        expected = agent_ids[turn % 3]
        assert next_agent == expected


@pytest.mark.asyncio
async def test_interview_mode_rotation():
    """In interview mode, even turns = interviewer (idx 0), odd turns = next interviewee."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4(), uuid4()]  # interviewer, interviewee1, interviewee2
    conv = _make_conversation(ConversationMode.INTERVIEW, agent_ids)

    from unittest.mock import AsyncMock, MagicMock
    db = AsyncMock()

    # Turn 0 (history=0, even): interviewer
    history = _mock_history(0)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = history
    db.execute.return_value = mock_result
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[0]

    # Turn 1 (history=1, odd): first interviewee
    history = _mock_history(1)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = history
    db.execute.return_value = mock_result
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[1]

    # Turn 2 (history=2, even): interviewer
    history = _mock_history(2)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = history
    db.execute.return_value = mock_result
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[0]

    # Turn 3 (history=3, odd): second interviewee
    history = _mock_history(3)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = history
    db.execute.return_value = mock_result
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[2]


@pytest.mark.asyncio
async def test_free_mode_wraps_around():
    """Free mode should wrap around when history exceeds agent count."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4()]
    conv = _make_conversation(ConversationMode.FREE, agent_ids)

    from unittest.mock import AsyncMock, MagicMock
    db = AsyncMock()

    # With 2 agents and history length 4: 4 % 2 = 0 -> first agent
    history = _mock_history(4)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = history
    db.execute.return_value = mock_result

    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[0]

    # With 2 agents and history length 5: 5 % 2 = 1 -> second agent
    history = _mock_history(5)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = history
    db.execute.return_value = mock_result

    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[1]
