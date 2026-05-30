import pytest
from httpx import AsyncClient

from app.models.agent import Agent
from app.models.model import Model


@pytest.mark.asyncio
async def test_create_match_accepts_frontend_payload(client: AsyncClient, db, setup_db):
    model = Model(name="Test Model", provider="mock", model_id="mock/model")
    db.add(model)
    await db.flush()
    agent_a = Agent(name="Agent A", model_id=model.id)
    agent_b = Agent(name="Agent B", model_id=model.id)
    db.add_all([agent_a, agent_b])
    await db.commit()

    resp = await client.post("/api/arena/matches", json={
        "match_type": "qa_pk",
        "prompt": "谁更适合做策略分析？",
        "agent_ids": [str(agent_a.id), str(agent_b.id)],
    })

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["match_type"] == "qa_pk"
    assert data["agent_a_id"] == str(agent_a.id)
    assert data["agent_b_id"] == str(agent_b.id)
    assert data["agent_a_name"] == "Agent A"
    assert data["agent_b_name"] == "Agent B"
    assert data["votes_a"] == 0
    assert data["votes_b"] == 0


@pytest.mark.asyncio
async def test_create_match_accepts_legacy_a_b_payload(client: AsyncClient, db, setup_db):
    model = Model(name="Test Model 2", provider="mock", model_id="mock/model")
    db.add(model)
    await db.flush()
    agent_a = Agent(name="Agent C", model_id=model.id)
    agent_b = Agent(name="Agent D", model_id=model.id)
    db.add_all([agent_a, agent_b])
    await db.commit()

    resp = await client.post("/api/arena/matches", json={
        "match_type": "qa",
        "prompt": "兼容旧前端字段",
        "agent_a_id": str(agent_a.id),
        "agent_b_id": str(agent_b.id),
    })

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["match_type"] == "qa_pk"
    assert data["agent_a_id"] == str(agent_a.id)
    assert data["agent_b_id"] == str(agent_b.id)


@pytest.mark.asyncio
async def test_list_games_empty_is_available(client: AsyncClient, setup_db):
    resp = await client.get("/api/games")

    assert resp.status_code == 200
    assert resp.json() == []
