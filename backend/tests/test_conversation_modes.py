import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.conversation import ConversationMode
from app.services.conversation_engine import ConversationEngine


def _make_conversation(mode: ConversationMode, agent_ids, max_turns=10):
    conv = MagicMock()
    conv.id = uuid4()
    conv.mode = mode
    conv.config = {"agent_ids": agent_ids, "max_turns": max_turns}
    conv.title = "Test"
    return conv


def _mock_agent(name="Agent"):
    agent = MagicMock()
    agent.id = uuid4()
    agent.name = name
    agent.model_id = uuid4()
    return agent


def _make_participant(name="Agent"):
    return {
        "agent": _mock_agent(name),
        "profile": None,
        "supports_vision": False,
        "model_id": "test-model",
        "api_key": None,
        "api_base": None,
    }


def test_pause_and_resume_preserve_running_state():
    engine = ConversationEngine()
    conversation_id = uuid4()
    key = str(conversation_id)
    engine._running[key] = True
    engine._cancelled[key] = False
    engine._paused[key] = False

    engine.pause(conversation_id)

    assert engine._running[key] is True
    assert engine._paused[key] is True
    assert engine._should_continue(key, 0, 1) is True

    engine.resume(conversation_id)

    assert engine._running[key] is True
    assert engine._paused[key] is False
    assert engine._should_continue(key, 0, 1) is True


@pytest.mark.asyncio
async def test_wait_if_paused_blocks_until_resume(monkeypatch):
    engine = ConversationEngine()
    conversation_id = uuid4()
    key = str(conversation_id)
    engine._running[key] = True
    engine._cancelled[key] = False
    engine._paused[key] = True

    sleeps = 0

    real_sleep = asyncio.sleep

    async def fake_sleep(_delay):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 2:
            engine.resume(conversation_id)
        await real_sleep(0)

    monkeypatch.setattr("app.services.conversation_engine.asyncio.sleep", fake_sleep)

    await engine._wait_if_paused(key)

    assert sleeps == 2
    assert engine._paused[key] is False


@pytest.mark.asyncio
async def test_free_mode_waits_when_paused_before_next_turn(monkeypatch):
    engine = ConversationEngine()
    participant = _make_participant()
    conversation = _make_conversation(ConversationMode.FREE, [participant["agent"].id], max_turns=1)
    key = str(conversation.id)
    engine._running[key] = True
    engine._cancelled[key] = False
    engine._paused[key] = True

    waited = False

    async def fake_wait(paused_key):
        nonlocal waited
        waited = True
        assert paused_key == key
        engine.resume(conversation.id)

    class SessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(engine, "_wait_if_paused", fake_wait)
    monkeypatch.setattr(engine, "_get_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(engine, "generate_reply", AsyncMock(return_value="hello"))
    monkeypatch.setattr(engine, "_save_message", AsyncMock())
    monkeypatch.setattr(engine, "_finalize_conversation", AsyncMock())
    monkeypatch.setattr("app.services.conversation_engine.async_session", lambda: SessionContext())
    monkeypatch.setattr("app.services.conversation_engine.asyncio.sleep", AsyncMock())

    await engine._run_free_mode(conversation, [participant])

    assert waited is True
    engine.generate_reply.assert_awaited_once()
    engine._save_message.assert_awaited_once()
    engine._finalize_conversation.assert_awaited_once_with(conversation, [participant], 1)
