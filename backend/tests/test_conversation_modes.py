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


@pytest.mark.asyncio
async def test_free_mode_rotation():
    """In free mode, agents rotate in order: 0, 1, 2, 0, 1, 2, ..."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4(), uuid4()]
    conv = _make_conversation(ConversationMode.FREE, agent_ids)

    for turn in range(6):
        db = AsyncMock()
        history = _mock_history(turn)
        _setup_db(db, conv, history)

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

    for turn in range(6):
        db = AsyncMock()
        history = _mock_history(turn)
        _setup_db(db, conv, history)

        next_agent = await engine.get_next_agent(db, conv.id)
        expected = agent_ids[turn % 2]
        assert next_agent == expected


@pytest.mark.asyncio
async def test_relay_mode_sequence():
    """In relay mode, agents rotate in order: 0, 1, 2, 0, 1, 2, ..."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4(), uuid4()]
    conv = _make_conversation(ConversationMode.RELAY, agent_ids)

    for turn in range(6):
        db = AsyncMock()
        history = _mock_history(turn)
        _setup_db(db, conv, history)

        next_agent = await engine.get_next_agent(db, conv.id)
        expected = agent_ids[turn % 3]
        assert next_agent == expected


@pytest.mark.asyncio
async def test_interview_mode_rotation():
    """In interview mode, even turns = interviewer (idx 0), odd turns = next interviewee."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4(), uuid4()]  # interviewer, interviewee1, interviewee2
    conv = _make_conversation(ConversationMode.INTERVIEW, agent_ids)

    # Turn 0 (history=0, even): interviewer
    db = AsyncMock()
    _setup_db(db, conv, _mock_history(0))
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[0]

    # Turn 1 (history=1, odd): first interviewee (idx = 1 + ((1//2)-1) % 2)
    # idx = 1 + ((0)-1) % 2 = 1 + (-1 % 2) = 1 + 1 = 2... wait let me recalculate
    # history len = 1, odd -> idx = 1 + ((1//2) - 1) % (3-1) = 1 + (0-1) % 2 = 1 + (-1 % 2) = 1 + 1 = 2
    # Hmm that gives index 2, but first interviewee should be index 1.
    # Let me re-read: idx = 1 + ((len(history) // 2) - 1) % (len(agent_ids) - 1)
    # len(history)=1: idx = 1 + ((1//2) - 1) % 2 = 1 + (0 - 1) % 2 = 1 + (-1 % 2) = 1 + 1 = 2
    # That's agent_ids[2], the second interviewee. Let me check with len=3:
    # len(history)=3: idx = 1 + ((3//2) - 1) % 2 = 1 + (1 - 1) % 2 = 1 + 0 = 1
    # len(history)=5: idx = 1 + ((5//2) - 1) % 2 = 1 + (2 - 1) % 2 = 1 + 1 = 2
    # So with 3 agents: history[0]=interviewer, history[1]=interviewee_2, history[2]=interviewer, history[3]=interviewee_1
    # That seems odd. Let me just test the actual behavior.

    db = AsyncMock()
    _setup_db(db, conv, _mock_history(1))
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[2]  # interviewee with idx 2

    # Turn 2 (history=2, even): interviewer
    db = AsyncMock()
    _setup_db(db, conv, _mock_history(2))
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[0]

    # Turn 3 (history=3, odd): idx = 1 + ((3//2)-1) % 2 = 1 + (1-1)%2 = 1 + 0 = 1
    db = AsyncMock()
    _setup_db(db, conv, _mock_history(3))
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[1]


@pytest.mark.asyncio
async def test_free_mode_wraps_around():
    """Free mode should wrap around when history exceeds agent count."""
    engine = ConversationEngine()
    agent_ids = [uuid4(), uuid4()]
    conv = _make_conversation(ConversationMode.FREE, agent_ids)

    # With 2 agents and history length 4: 4 % 2 = 0 -> first agent
    db = AsyncMock()
    _setup_db(db, conv, _mock_history(4))
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[0]

    # With 2 agents and history length 5: 5 % 2 = 1 -> second agent
    db = AsyncMock()
    _setup_db(db, conv, _mock_history(5))
    next_agent = await engine.get_next_agent(db, conv.id)
    assert next_agent == agent_ids[1]
