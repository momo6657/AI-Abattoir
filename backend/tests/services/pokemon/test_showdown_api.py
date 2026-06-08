"""API tests for Pokemon Showdown command and parse helpers."""

import json

import pytest

from app.api import pokemon as pokemon_api
from app.schemas.pokemon import ShowdownSessionMissionRequest
from app.services.pokemon.showdown_learning_store import pokemon_showdown_learning_store
from app.services.pokemon.knowledge_service import pokemon_knowledge_service


@pytest.mark.asyncio
async def test_showdown_commands_build_ladder_search(client):
    response = await client.post(
        "/api/pokemon/showdown/commands",
        json={
            "action": "ladder_search",
            "battle_format": "gen9vgc2024regg",
            "team": [
                {
                    "species": "Incineroar",
                    "ability": "Intimidate",
                    "item": "Sitrus Berry",
                    "moves": ["Fake Out", "Flare Blitz"],
                    "level": 50,
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["commands"][0].startswith("|/utm Incineroar||sitrusberry|intimidate|fakeout,flareblitz")
    assert data["commands"][1] == "|/search gen9vgc2024regg"


@pytest.mark.asyncio
async def test_pokemon_formats_endpoint_returns_showdown_metadata(client):
    response = await client.get("/api/pokemon/formats")

    assert response.status_code == 200
    data = response.json()
    assert any(item["id"] == "vgc2024" and item["showdown_format"] == "gen9vgc2024regg" for item in data)
    assert any(item["id"] == "gen9randombattle" and not item["requires_team"] for item in data)


@pytest.mark.asyncio
async def test_pokemon_format_detail_resolves_alias(client):
    response = await client.get("/api/pokemon/formats/gen9vgc2024regg")

    assert response.status_code == 200
    assert response.json()["id"] == "vgc2024"


@pytest.mark.asyncio
async def test_showdown_commands_reject_invalid_choose_slot(client):
    response = await client.post(
        "/api/pokemon/showdown/commands",
        json={"action": "choose_move", "room_id": "battle-gen9vgc-1", "move_slot": 0},
    )

    assert response.status_code == 400
    assert "1-based" in response.json()["detail"]


@pytest.mark.asyncio
async def test_showdown_parse_extracts_battle_request(client):
    payload = {
        "rqid": 9,
        "active": [{"moves": [{"id": "protect", "target": "self"}]}],
        "side": {"pokemon": [{"ident": "p1: Incineroar"}]},
    }

    response = await client.post(
        "/api/pokemon/showdown/parse",
        json={"payload": f">battle-gen9vgc-42\n|request|{json.dumps(payload)}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["events"][0]["event_type"] == "request"
    assert data["battle_request"]["room_id"] == "battle-gen9vgc-42"
    assert data["battle_request"]["request_id"] == 9
    assert data["battle_request"]["needs_choice"]


@pytest.mark.asyncio
async def test_showdown_decision_plans_next_choice_from_payload(client):
    payload = {
        "rqid": 10,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }

    response = await client.post(
        "/api/pokemon/showdown/decision",
        json={"payload": f">battle-gen9vgc-43\n|request|{json.dumps(payload)}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["decision_type"] == "move"
    assert data["plan"]["command"] == "battle-gen9vgc-43|/choose move 2 -1|10"
    assert data["plan"]["needs_choice"]


@pytest.mark.asyncio
async def test_showdown_decision_accepts_learning_profile(client):
    payload = {
        "rqid": 20,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }

    response = await client.post(
        "/api/pokemon/showdown/decision",
        json={
            "request": payload,
            "room_id": "battle-gen9vgc-45",
            "learning_profile": {
                "battles": 3,
                "win_rate": 0.0,
                "average_reward": 10.0,
                "faints_for": 1,
                "faints_against": 5,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["command"] == "battle-gen9vgc-45|/choose move 1|20"
    assert data["plan"]["choice_details"][0]["move"] == "protect"
    assert data["plan"]["choice_details"][0]["learning_used"]


@pytest.mark.asyncio
async def test_showdown_decision_accepts_team_context_for_preview(client):
    payload = {
        "rqid": 23,
        "teamPreview": True,
        "maxTeamSize": 4,
        "side": {
            "pokemon": [
                {"ident": "p1: Flutter Mane", "condition": "100/100"},
                {"ident": "p1: Amoonguss", "condition": "100/100"},
                {"ident": "p1: Incineroar", "condition": "100/100"},
                {"ident": "p1: Tornadus", "condition": "100/100"},
            ]
        },
    }

    response = await client.post(
        "/api/pokemon/showdown/decision",
        json={
            "request": payload,
            "room_id": "battle-gen9vgc-46",
            "team_context": [
                {"species": "Flutter Mane", "moves": ["Moonblast"]},
                {"species": "Amoonguss", "moves": ["Spore", "Protect"]},
                {"species": "Incineroar", "ability": "Intimidate", "moves": ["Fake Out"]},
                {"species": "Tornadus", "moves": ["Tailwind"]},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["command"] == "battle-gen9vgc-46|/choose team 3421|23"
    assert data["plan"]["choice_details"][0]["pokemon"] == "Incineroar"
    assert data["plan"]["choice_details"][0]["strategy_used"]


@pytest.mark.asyncio
async def test_showdown_decision_accepts_battlefield_context_for_targeting(client):
    payload = {
        "rqid": 24,
        "active": [
            {
                "moves": [
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }

    response = await client.post(
        "/api/pokemon/showdown/decision",
        json={
            "request": payload,
            "room_id": "battle-gen9vgc-47",
            "active_pokemon": 2,
            "battlefield_context": {
                "opponents": [
                    {"position": "a", "active": True, "fainted": False, "hp_fraction": 0.8},
                    {"position": "b", "active": True, "fainted": False, "hp_fraction": 0.2},
                ]
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["command"] == "battle-gen9vgc-47|/choose move 1 -2|24"
    assert data["plan"]["choice_details"][0]["target"] == -2


@pytest.mark.asyncio
async def test_showdown_decision_accepts_knowledge_context(client):
    payload = {
        "rqid": 18,
        "active": [
            {
                "moves": [
                    {"id": "flareblitz", "target": "normal", "basePower": 80, "pp": 15},
                    {"id": "knockoff", "target": "normal", "basePower": 75, "pp": 20},
                ]
            }
        ],
        "side": {
            "pokemon": [
                {"ident": "p1: Incineroar, L50, M", "condition": "100/100", "active": True},
            ]
        },
    }

    response = await client.post(
        "/api/pokemon/showdown/decision",
        json={
            "request": payload,
            "room_id": "battle-gen9vgc-44",
            "knowledge_context": {
                "members": [
                    {
                        "species": "Incineroar",
                        "results": [{"title": "Incineroar VGC usage recommends Knock Off"}],
                    }
                ]
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["command"] == "battle-gen9vgc-44|/choose move 2 -1|18"
    assert data["plan"]["choice_details"][0]["knowledge_used"]


@pytest.mark.asyncio
async def test_showdown_decision_accepts_singles_active_count(client):
    payload = {
        "rqid": 19,
        "active": [
            {
                "moves": [
                    {"id": "shadowball", "target": "normal", "basePower": 80, "pp": 15},
                    {"id": "protect", "target": "self", "pp": 16},
                ]
            }
        ],
    }

    response = await client.post(
        "/api/pokemon/showdown/decision",
        json={
            "request": payload,
            "room_id": "battle-gen9ou-2",
            "active_pokemon": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["command"] == "battle-gen9ou-2|/choose move 1|19"
    assert data["plan"]["choice_details"][0]["target"] is None


@pytest.mark.asyncio
async def test_showdown_decision_requires_payload_or_request(client):
    response = await client.post("/api/pokemon/showdown/decision", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "payload or request is required."


@pytest.mark.asyncio
async def test_team_knowledge_endpoint_returns_batch_context(setup_db, monkeypatch, client):
    async def fake_search(db, query_type, query_key, max_results=5):
        return {
            "cached": query_key == "Incineroar",
            "query_type": query_type,
            "query_key": query_key,
            "results": [{"title": f"{query_key} usage", "url": f"https://example.com/{query_key}"}],
        }

    monkeypatch.setattr(pokemon_knowledge_service, "search", fake_search)

    response = await client.post(
        "/api/pokemon/knowledge/team",
        json={"species": ["Incineroar", "Flutter Mane", "Incineroar"], "max_results": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["species"] == ["Incineroar", "Flutter Mane"]
    assert data["member_count"] == 2
    assert data["cached_count"] == 1
    assert data["result_count"] == 2
    assert data["sources"] == ["https://example.com/Incineroar", "https://example.com/Flutter Mane"]


@pytest.mark.asyncio
async def test_team_knowledge_endpoint_validates_payload(client):
    response = await client.post("/api/pokemon/knowledge/team", json={"species": [], "max_results": 3})

    assert response.status_code == 400
    assert response.json()["detail"] == "species is required."


@pytest.mark.asyncio
async def test_showdown_session_processes_payload_and_returns_commands(setup_db, client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "battle_format": "gen9vgc2024regg", "login_assertion": "ASSERT"},
    )
    assert created.status_code == 200
    created_data = created.json()
    session_id = created_data["session_id"]
    assert created_data["mode"] == "balanced"
    assert created_data["requested_mode"] == "balanced"
    assert created_data["mode_source"] == "manual"
    assert created_data["team_source"] == "template"
    assert len(created_data["team_species"]) == 4
    request = {
        "rqid": 21,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }

    response = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/message",
        json={"payload": f"|challstr|1|abc\n>battle-gen9vgc-99\n|request|{json.dumps(request)}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["commands"] == ["|/trn Bot,0,ASSERT", "battle-gen9vgc-99|/choose move 2 -1|21"]
    assert data["session"]["status"] == "responded"
    assert data["session"]["analysis"]["decision_count"] == 1

    finished = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/message",
        json={"payload": ">battle-gen9vgc-99\n|win|Bot", "auto_respond": False},
    )
    assert finished.status_code == 200
    finished_data = finished.json()
    assert finished_data["learning_profile"]["battles"] == 1
    assert finished_data["session"]["learning_profile"]["battles"] == 1
    assert finished_data["session"]["learning_profile"]["wins"] == 1

    deleted = await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_showdown_session_auto_mode_uses_learning_recommendation(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="auto-mode-seed",
        username="Bot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="aggressive",
        analysis={"status": "win", "reward": 140.0, "turns": 4, "faints_for": 2, "faints_against": 0},
        decisions=[{"decision_type": "move"}],
    )

    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "battle_format": "vgc2024", "mode": "auto"},
    )

    assert created.status_code == 200
    data = created.json()
    assert data["requested_mode"] == "auto"
    assert data["mode"] == "aggressive"
    assert data["mode_source"] == "learning_profile"
    assert data["mode_recommendation"]["mode"] == "aggressive"
    assert data["team_source"] == "template"
    assert len(data["team_species"]) == 4

    await client.delete(f"/api/pokemon/showdown/sessions/{data['session_id']}")


@pytest.mark.asyncio
async def test_showdown_session_auto_team_uses_weak_learning_profile(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="weak-team-seed-1",
        username="Bot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="balanced",
        analysis={"status": "loss", "reward": 10.0, "turns": 4, "faints_for": 1, "faints_against": 4},
        decisions=[{"decision_type": "move"}],
    )

    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "battle_format": "vgc2024", "mode": "balanced"},
    )

    assert created.status_code == 200
    data = created.json()
    assert data["team_source"] == "learned_template"
    assert data["team_adjustments"]
    assert any(adjustment["title"] == "Added Protect safety" for adjustment in data["team_adjustments"])

    await client.delete(f"/api/pokemon/showdown/sessions/{data['session_id']}")


@pytest.mark.asyncio
async def test_showdown_session_create_accepts_auto_login_without_leaking_password(setup_db, client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={
            "username": "Bot",
            "team": None,
            "auto_login": True,
            "login_password": "SECRET",
        },
    )

    assert created.status_code == 200
    data = created.json()
    assert data["auto_login"]
    assert data["has_login_password"]
    assert not data["has_login_assertion"]
    assert "SECRET" not in json.dumps(data)

    await client.delete(f"/api/pokemon/showdown/sessions/{data['session_id']}")


@pytest.mark.asyncio
async def test_showdown_session_create_can_auto_research_team(setup_db, monkeypatch, client):
    async def fake_search_team(db, species, query_type="species_usage", max_results=3):
        return {
            "query_type": query_type,
            "species": species,
            "members": [{"species": species[0], "results": [{"title": "usage"}], "result_count": 1}],
            "member_count": len(species),
            "cached_count": 0,
            "result_count": 1,
            "failed_count": 0,
            "sources": ["https://example.com/usage"],
        }

    monkeypatch.setattr(pokemon_knowledge_service, "search_team", fake_search_team)

    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "auto_research_team": True},
    )

    assert created.status_code == 200
    data = created.json()
    assert data["auto_research_team"]
    assert data["has_knowledge_context"]
    assert data["knowledge_context"]["result_count"] == 1
    assert data["knowledge_context"]["sources"] == ["https://example.com/usage"]

    await client.delete(f"/api/pokemon/showdown/sessions/{data['session_id']}")


@pytest.mark.asyncio
async def test_showdown_session_search_endpoint_records_commands(setup_db, client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": [{"species": "Incineroar", "ability": "Intimidate", "moves": ["Fake Out"]}]},
    )
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/search")

    assert response.status_code == 200
    data = response.json()
    assert data["commands"][0].startswith("|/utm Incineroar||")
    assert data["commands"][1] == "|/search gen9vgc2024regg"
    assert data["session"]["status"] == "searching"

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_knowledge_endpoint_attaches_context(setup_db, monkeypatch, client):
    async def fake_search_team(db, species, query_type="species_usage", max_results=3):
        return {
            "query_type": query_type,
            "species": species,
            "members": [{"species": species[0], "results": [{"url": "https://example.com/a"}], "result_count": 1}],
            "member_count": len(species),
            "cached_count": 0,
            "result_count": 1,
            "failed_count": 0,
            "sources": ["https://example.com/a"],
        }

    monkeypatch.setattr(pokemon_knowledge_service, "search_team", fake_search_team)
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/knowledge", params={"max_results": 2})

    assert response.status_code == 200
    data = response.json()
    assert data["knowledge_context"]["result_count"] == 1
    assert data["session"]["has_knowledge_context"]
    assert data["session"]["knowledge_context"]["sources"] == ["https://example.com/a"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_next_action_defaults_to_recommended_research(setup_db, monkeypatch, client):
    async def fake_search_team(db, species, query_type="species_usage", max_results=3):
        return {
            "query_type": query_type,
            "species": species,
            "members": [{"species": species[0], "results": [{"title": "usage"}], "result_count": 1}],
            "member_count": len(species),
            "cached_count": 0,
            "result_count": 1,
            "failed_count": 0,
            "sources": ["https://example.com/usage"],
        }

    monkeypatch.setattr(pokemon_knowledge_service, "search_team", fake_search_team)
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/next-action", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "research_team"
    assert data["knowledge_context"]["result_count"] == 1
    assert data["session"]["has_knowledge_context"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_next_action_can_queue_search(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/next-action",
        json={"action": "start_search"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "start_search"
    assert data["result"]["commands"][1] == "|/search gen9vgc2024regg"
    assert data["session"]["status"] == "searching"
    assert data["session"]["pending_command_count"] == 2

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_next_action_can_create_next_session(setup_db, client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "mode": "auto", "login_password": "SECRET"},
    )
    previous_id = created.json()["session_id"]

    response = await client.post(
        f"/api/pokemon/showdown/sessions/{previous_id}/next-action",
        json={"action": "new_session"},
    )

    assert response.status_code == 200
    data = response.json()
    next_id = data["session"]["session_id"]
    assert data["action"] == "new_session"
    assert next_id != previous_id
    assert data["result"]["previous_session"]["session_id"] == previous_id
    assert data["session"]["requested_mode"] == "auto"
    assert "SECRET" not in json.dumps(data)

    await client.delete(f"/api/pokemon/showdown/sessions/{previous_id}")
    await client.delete(f"/api/pokemon/showdown/sessions/{next_id}")


@pytest.mark.asyncio
async def test_showdown_session_next_action_rejects_unknown_action(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/next-action",
        json={"action": "unsupported"},
    )

    assert response.status_code == 400
    assert "Unsupported Showdown next action" in response.json()["detail"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_supervisor_runs_allowed_recommendations(setup_db, monkeypatch, client):
    async def fake_search_team(db, species, query_type="species_usage", max_results=3):
        return {
            "query_type": query_type,
            "species": species,
            "members": [{"species": species[0], "results": [{"title": "usage"}], "result_count": 1}],
            "member_count": len(species),
            "cached_count": 0,
            "result_count": 1,
            "failed_count": 0,
            "sources": ["https://example.com/usage"],
        }

    monkeypatch.setattr(pokemon_knowledge_service, "search_team", fake_search_team)
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/supervise",
        json={"max_actions": 2, "allowed_actions": ["research_team", "start_search"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["stop_reason"] == "max_actions"
    assert data["step_count"] == 2
    assert [step["action"] for step in data["steps"]] == ["research_team", "start_search"]
    assert data["knowledge_context"]["result_count"] == 1
    assert data["session"]["status"] == "searching"
    assert data["session"]["pending_command_count"] == 2
    assert data["supervisor_summary"]["actions"] == ["research_team", "start_search"]
    assert data["supervisor_summary"]["supervisor_number"] == 1
    assert data["session"]["last_supervisor_summary"]["stop_reason"] == "max_actions"
    assert data["session"]["supervisor_history_count"] == 1

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_supervisor_can_advance_to_new_session(setup_db, client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "mode": "auto", "login_password": "SECRET"},
    )
    previous_id = created.json()["session_id"]
    marked_finished = await client.post(
        f"/api/pokemon/showdown/sessions/{previous_id}/message",
        json={"payload": ">battle-gen9vgc-91\n|win|Bot", "auto_respond": False},
    )
    assert marked_finished.status_code == 200
    assert marked_finished.json()["session"]["status"] == "finished"

    response = await client.post(
        f"/api/pokemon/showdown/sessions/{previous_id}/supervise",
        json={"max_actions": 3, "allowed_actions": ["new_session"]},
    )

    assert response.status_code == 200
    data = response.json()
    next_id = data["session"]["session_id"]
    assert data["stop_reason"] == "new_session"
    assert data["step_count"] == 1
    assert data["steps"][0]["action"] == "new_session"
    assert data["original_session_id"] == previous_id
    assert data["session_id"] == next_id
    assert next_id != previous_id
    assert data["supervisor_summary"]["session_id"] == next_id
    assert data["session"]["last_supervisor_summary"]["last_action"] == "new_session"
    assert "SECRET" not in json.dumps(data)

    await client.delete(f"/api/pokemon/showdown/sessions/{previous_id}")
    await client.delete(f"/api/pokemon/showdown/sessions/{next_id}")


@pytest.mark.asyncio
async def test_showdown_session_supervisor_rejects_invalid_action_limit(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/supervise",
        json={"max_actions": 0},
    )

    assert response.status_code == 400
    assert "max_actions must be between 1 and 20" in response.json()["detail"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_mission_creates_session_and_runs_supervisor(setup_db, monkeypatch, client):
    async def fake_search_team(db, species, query_type="species_usage", max_results=3):
        return {
            "query_type": query_type,
            "species": species,
            "members": [{"species": species[0], "results": [{"title": "usage"}], "result_count": 1}],
            "member_count": len(species),
            "cached_count": 0,
            "result_count": 1,
            "failed_count": 0,
            "sources": ["https://example.com/usage"],
        }

    monkeypatch.setattr(pokemon_knowledge_service, "search_team", fake_search_team)

    response = await client.post(
        "/api/pokemon/showdown/mission",
        json={
            "username": "MissionBot",
            "team": None,
            "mode": "auto",
            "auto_research_team": True,
            "max_actions": 1,
            "allowed_actions": ["start_search"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    session_id = data["session"]["session_id"]
    assert data["mission_summary"]["username"] == "MissionBot"
    assert data["mission_summary"]["step_count"] == 1
    assert data["mission_summary"]["mission_goal"] == "ladder"
    assert data["mission_summary"]["allowed_actions"] == ["start_search"]
    assert data["mission_summary"]["mission_number"] == 1
    assert data["supervisor"]["steps"][0]["action"] == "start_search"
    assert data["session"]["status"] == "searching"
    assert data["session"]["has_knowledge_context"]
    assert data["session"]["last_supervisor_summary"]["actions"] == ["start_search"]
    assert data["session"]["last_mission_summary"]["mission_goal"] == "ladder"
    assert data["session"]["mission_history_count"] == 1

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_mission_prepare_goal_only_researches_team(setup_db, monkeypatch, client):
    async def fake_search_team(db, species, query_type="species_usage", max_results=3):
        return {
            "query_type": query_type,
            "species": species,
            "members": [{"species": species[0], "results": [{"title": "usage"}], "result_count": 1}],
            "member_count": len(species),
            "cached_count": 0,
            "result_count": 1,
            "failed_count": 0,
            "sources": ["https://example.com/usage"],
        }

    monkeypatch.setattr(pokemon_knowledge_service, "search_team", fake_search_team)

    response = await client.post(
        "/api/pokemon/showdown/mission",
        json={
            "username": "PrepBot",
            "team": None,
            "mission_goal": "prepare",
            "max_actions": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    session_id = data["session"]["session_id"]
    assert data["mission_summary"]["mission_goal"] == "prepare"
    assert data["mission_summary"]["allowed_actions"] == ["research_team"]
    assert data["mission_summary"]["stop_reason"] == "stop_action"
    assert data["mission_summary"]["mission_number"] == 1
    assert data["supervisor"]["steps"][0]["action"] == "research_team"
    assert data["session"]["status"] == "ready"
    assert data["session"]["pending_command_count"] == 0
    assert data["session"]["has_knowledge_context"]
    assert data["session"]["last_mission_summary"]["allowed_actions"] == ["research_team"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_mission_plan_returns_next_request_from_learning_profile(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="planned-preview-win",
        username="PlanPreviewBot",
        battle_format="gen9randombattle",
        showdown_format="gen9randombattle",
        mode="aggressive",
        analysis={"status": "win", "reward": 125.0, "turns": 5, "faints_for": 3, "faints_against": 1},
        decisions=[{"decision_type": "move"}],
    )

    response = await client.post(
        "/api/pokemon/showdown/mission/plan",
        json={
            "username": "PlanPreviewBot",
            "battle_format": "gen9randombattle",
            "mode": "auto",
            "mission_goal": "auto",
            "login_password": "secret",
            "max_actions": 4,
            "max_messages": 12,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mission_goal"] == "learn"
    assert data["mission_goal_source"] == "training_plan"
    assert data["action_plan_source"] == "training_plan"
    assert data["mission_request"]["mission_goal"] == "auto"
    assert data["mission_request"]["battle_format"] == "gen9randombattle"
    assert data["mission_request"]["max_actions"] == 4
    assert data["mission_request"]["max_messages"] == 12
    assert "login_password" not in data["mission_request"]
    assert data["executable_plan_actions"] == [
        "connect",
        "flush_pending",
        "start_search",
        "autopilot",
        "analyze",
        "new_session",
    ]


@pytest.mark.asyncio
async def test_showdown_mission_plan_prepares_generated_team_without_knowledge(setup_db, client):
    response = await client.post(
        "/api/pokemon/showdown/mission/plan",
        json={
            "username": "PlanPreviewBot",
            "battle_format": "vgc2024",
            "mission_goal": "auto",
            "max_actions": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mission_goal"] == "prepare"
    assert data["mission_goal_source"] == "knowledge_precheck"
    assert data["allowed_actions"] == ["research_team"]
    assert data["mission_request"]["auto_search"] is False


@pytest.mark.asyncio
async def test_showdown_training_chain_runs_adaptive_planned_rounds(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="chain-preview-win",
        username="ChainBot",
        battle_format="gen9randombattle",
        showdown_format="gen9randombattle",
        mode="aggressive",
        analysis={"status": "win", "reward": 130.0, "turns": 4, "faints_for": 3, "faints_against": 0},
        decisions=[{"decision_type": "move"}],
    )

    response = await client.post(
        "/api/pokemon/showdown/training-chain",
        json={
            "username": "ChainBot",
            "battle_format": "gen9randombattle",
            "mode": "auto",
            "mission_goal": "auto",
            "rounds": 2,
            "max_actions": 1,
            "allowed_actions": ["start_search"],
            "stop_on_finished": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requested_rounds"] == 2
    assert data["completed_rounds"] == 2
    assert data["stop_reason"] == "round_limit"
    assert data["learning_profile"]["training_plan"]["next_mission_goal"] == "learn"
    assert data["mastery_score"] > 0
    assert [round_item["planned_goal"] for round_item in data["rounds"]] == ["learn", "learn"]
    assert all(round_item["planned_goal_source"] == "training_plan" for round_item in data["rounds"])
    assert all(round_item["action_plan_source"] == "custom" for round_item in data["rounds"])
    assert all(round_item["supervisor_step_count"] == 1 for round_item in data["rounds"])
    assert all(round_item["mission_summary"]["allowed_actions"] == ["start_search"] for round_item in data["rounds"])
    assert data["progress"]["before_mastery_score"] > 0
    assert data["progress"]["after_mastery_score"] == data["mastery_score"]
    assert data["progress"]["battle_delta"] == 0
    assert data["progress"]["direction"] == "unchanged"
    assert data["training_chain_summary"]["chain_number"] == 1
    assert data["training_chain_summary"]["completed_rounds"] == 2
    assert data["training_chain_summary"]["progress"]["after_mastery_score"] == data["mastery_score"]
    assert data["training_chain_summary"]["rounds"][-1]["planned_goal"] == "learn"
    assert data["final_session"]["last_training_chain_summary"]["completed_rounds"] == 2
    assert data["final_session"]["training_chain_history_count"] == 1
    assert data["final_session"]["training_chain_trend"]["chain_count"] == 1
    assert data["final_session"]["training_chain_trend"]["direction"] in {"flat", "improving"}

    for round_item in data["rounds"]:
        await client.delete(f"/api/pokemon/showdown/sessions/{round_item['session_id']}")


@pytest.mark.asyncio
async def test_showdown_training_chain_stops_on_mastery_target(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="chain-target-win",
        username="TargetBot",
        battle_format="gen9randombattle",
        showdown_format="gen9randombattle",
        mode="balanced",
        analysis={"status": "win", "reward": 100.0, "turns": 7, "faints_for": 2, "faints_against": 1},
        decisions=[{"decision_type": "move"}],
    )

    response = await client.post(
        "/api/pokemon/showdown/training-chain",
        json={
            "username": "TargetBot",
            "battle_format": "gen9randombattle",
            "mission_goal": "auto",
            "rounds": 5,
            "max_actions": 1,
            "allowed_actions": ["start_search"],
            "mastery_score_target": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["completed_rounds"] == 1
    assert data["stop_reason"] == "mastery_score_target"
    assert data["rounds"][0]["mastery_score"] >= 1

    await client.delete(f"/api/pokemon/showdown/sessions/{data['rounds'][0]['session_id']}")


@pytest.mark.asyncio
async def test_showdown_mission_auto_goal_resolves_from_session_state(setup_db, monkeypatch, client):
    async def fake_search_team(db, species, query_type="species_usage", max_results=3):
        return {
            "query_type": query_type,
            "species": species,
            "members": [{"species": species[0], "results": [{"title": "usage"}], "result_count": 1}],
            "member_count": len(species),
            "cached_count": 0,
            "result_count": 1,
            "failed_count": 0,
            "sources": ["https://example.com/usage"],
        }

    monkeypatch.setattr(pokemon_knowledge_service, "search_team", fake_search_team)

    response = await client.post(
        "/api/pokemon/showdown/mission",
        json={
            "username": "AutoMissionBot",
            "team": None,
            "mission_goal": "auto",
            "max_actions": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    session_id = data["session"]["session_id"]
    assert data["mission_summary"]["requested_mission_goal"] == "auto"
    assert data["mission_summary"]["mission_goal"] == "prepare"
    assert data["mission_summary"]["mission_goal_source"] == "knowledge_precheck"
    assert data["mission_summary"]["allowed_actions"] == ["research_team"]
    assert data["mission_summary"]["training_plan"]["stage"] == "collect_data"
    assert data["mission_summary"]["training_plan"]["next_mission_goal"] == "queue"
    assert data["session"]["last_mission_summary"]["mission_goal"] == "prepare"
    assert data["session"]["has_knowledge_context"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_mission_auto_goal_uses_training_plan(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="planned-auto-win",
        username="PlanBot",
        battle_format="gen9randombattle",
        showdown_format="gen9randombattle",
        mode="aggressive",
        analysis={"status": "win", "reward": 120.0, "turns": 6, "faints_for": 3, "faints_against": 1},
        decisions=[{"decision_type": "move"}],
    )

    response = await client.post(
        "/api/pokemon/showdown/mission",
        json={
            "username": "PlanBot",
            "battle_format": "gen9randombattle",
            "team": None,
            "mode": "auto",
            "mission_goal": "auto",
            "max_actions": 1,
            "allowed_actions": ["start_search"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    session_id = data["session"]["session_id"]
    assert data["mission_summary"]["requested_mission_goal"] == "auto"
    assert data["mission_summary"]["mission_goal"] == "learn"
    assert data["mission_summary"]["mission_goal_source"] == "training_plan"
    assert data["mission_summary"]["action_plan_source"] == "custom"
    assert data["mission_summary"]["training_plan_actions"] == ["start_search", "autopilot", "analyze", "new_session"]
    assert data["mission_summary"]["executable_plan_actions"] == [
        "connect",
        "flush_pending",
        "start_search",
        "autopilot",
        "analyze",
        "new_session",
    ]
    assert data["mission_summary"]["training_plan"]["stage"] == "exploit"
    assert data["mission_summary"]["training_plan"]["next_mission_goal"] == "learn"
    assert data["session"]["last_mission_summary"]["mission_goal_source"] == "training_plan"

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


def test_showdown_auto_policy_translates_training_plan_actions():
    payload = ShowdownSessionMissionRequest(
        username="PolicyBot",
        battle_format="gen9randombattle",
        mission_goal="auto",
    )
    session = {
        "has_knowledge_context": False,
        "team_species": [],
        "learning_profile": {
            "battles": 3,
            "win_rate": 0.75,
            "average_reward": 95.0,
            "training_plan": {
                "next_mission_goal": "learn",
                "actions": ["start_search", "autopilot", "analyze", "new_session"],
                "reason": "Continue collecting strong ladder samples.",
            },
        },
    }

    policy = pokemon_api._resolve_showdown_mission_policy(payload, session)

    assert policy["mission_goal"] == "learn"
    assert policy["mission_goal_source"] == "training_plan"
    assert policy["action_plan_source"] == "training_plan"
    assert policy["allowed_actions"] == [
        "connect",
        "flush_pending",
        "start_search",
        "autopilot",
        "analyze",
        "new_session",
    ]
    assert policy["training_plan_actions"] == ["start_search", "autopilot", "analyze", "new_session"]
    assert policy["unsupported_plan_actions"] == []


def test_showdown_auto_policy_maps_abstract_training_actions():
    payload = ShowdownSessionMissionRequest(
        username="WeakPolicyBot",
        battle_format="gen9randombattle",
        mission_goal="auto",
    )
    session = {
        "has_knowledge_context": False,
        "team_species": [],
        "learning_profile": {
            "battles": 3,
            "win_rate": 0.1,
            "average_reward": 20.0,
            "training_plan": {
                "next_mission_goal": "prepare",
                "actions": ["research_team", "audit_switch", "plan_adjustments", "queue_short_run"],
                "reason": "Stabilize weak battle results.",
            },
        },
    }

    policy = pokemon_api._resolve_showdown_mission_policy(payload, session)

    assert policy["mission_goal"] == "prepare"
    assert policy["allowed_actions"] == [
        "research_team",
        "analyze",
        "connect",
        "flush_pending",
        "start_search",
        "autopilot",
    ]
    assert policy["unsupported_plan_actions"] == []


def test_showdown_training_chain_progress_marks_improvement():
    progress = pokemon_api._build_showdown_training_chain_progress(
        baseline_learning_profile={"battles": 2},
        baseline_mastery_score=120.0,
        latest_learning_profile={"battles": 3},
        latest_mastery_score=160.25,
    )

    assert progress["before_mastery_score"] == 120.0
    assert progress["after_mastery_score"] == 160.25
    assert progress["mastery_score_delta"] == 40.25
    assert progress["battle_delta"] == 1
    assert progress["direction"] == "improved"
    assert progress["improved"] is True


def test_showdown_training_chain_progress_marks_decline():
    progress = pokemon_api._build_showdown_training_chain_progress(
        baseline_learning_profile={"battles": 1},
        baseline_mastery_score=200.0,
        latest_learning_profile={"battles": 2},
        latest_mastery_score=190.0,
    )

    assert progress["mastery_score_delta"] == -10.0
    assert progress["battle_delta"] == 1
    assert progress["direction"] == "declined"
    assert progress["improved"] is False


def test_showdown_training_chain_progress_keeps_zero_latest_score():
    progress = pokemon_api._build_showdown_training_chain_progress(
        baseline_learning_profile={"battles": 1},
        baseline_mastery_score=25.0,
        latest_learning_profile={"battles": 2},
        latest_mastery_score=0.0,
    )

    assert progress["after_mastery_score"] == 0.0
    assert progress["mastery_score_delta"] == -25.0
    assert progress["direction"] == "declined"


@pytest.mark.asyncio
async def test_showdown_mission_rejects_invalid_supervisor_limit(setup_db, client):
    response = await client.post(
        "/api/pokemon/showdown/mission",
        json={"username": "MissionBot", "team": None, "max_actions": 0},
    )

    assert response.status_code == 400
    assert "max_actions must be between 1 and 20" in response.json()["detail"]


@pytest.mark.asyncio
async def test_showdown_mission_rejects_unknown_goal(setup_db, client):
    response = await client.post(
        "/api/pokemon/showdown/mission",
        json={"username": "MissionBot", "team": None, "mission_goal": "chaos"},
    )

    assert response.status_code == 400
    assert "mission_goal must be one of" in response.json()["detail"]


@pytest.mark.asyncio
async def test_showdown_session_cancel_search_endpoint_records_command(setup_db, client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "auto_search": True},
    )
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/cancel-search")

    assert response.status_code == 200
    data = response.json()
    assert data["commands"] == ["|/cancelsearch"]
    assert data["session"]["status"] == "ready"
    assert data["session"]["last_command"] == "|/cancelsearch"
    assert data["session"]["pending_command_count"] == 3

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_challenge_endpoints_queue_commands(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]
    updated = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/message",
        json={
            "payload": '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg"}}',
            "auto_respond": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["session"]["challenge_usernames"] == ["rival"]

    accepted = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/accept-challenge")
    rejected = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/reject-challenge",
        params={"username": "rival"},
    )

    assert accepted.status_code == 200
    assert accepted.json()["commands"][0].startswith("|/utm ")
    assert accepted.json()["commands"][1] == "|/accept rival"
    assert accepted.json()["session"]["status"] == "challenge_accepted"
    assert rejected.status_code == 200
    assert rejected.json()["commands"] == ["|/reject rival"]
    assert rejected.json()["session"]["pending_command_count"] == 3

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_auto_accepts_matching_challenge(setup_db, client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "auto_accept_challenges": True},
    )
    session_id = created.json()["session_id"]
    assert created.json()["auto_accept_challenges"]

    updated = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/message",
        json={
            "payload": '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg","ou-rival":"gen9ou"}}',
            "auto_respond": False,
        },
    )

    assert updated.status_code == 200
    data = updated.json()
    assert data["commands"][0].startswith("|/utm ")
    assert data["commands"][1] == "|/accept rival"
    assert data["session"]["accepted_challenges"] == ["rival"]
    assert data["session"]["pending_command_count"] == 2

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_accept_challenge_requires_challenger(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/accept-challenge")

    assert response.status_code == 400
    assert "No incoming Pokemon Showdown challenge" in response.json()["detail"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_flush_requires_connected_socket(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None, "auto_search": True})
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/flush")

    assert response.status_code == 400
    assert "websocket is not connected" in response.json()["detail"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_analysis_endpoint_returns_learning_signals(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/message",
        json={
            "payload": (
                ">battle-gen9vgc-100\n"
                "|player|p1|Bot\n"
                "|player|p2|Rival\n"
                "|turn|1\n"
                "|move|p1a: Flutter Mane|Moonblast|p2a: Urshifu\n"
                "|faint|p2a: Urshifu\n"
                "|win|Bot"
            ),
            "auto_respond": False,
        },
    )
    assert response.status_code == 200

    analysis = await client.get(f"/api/pokemon/showdown/sessions/{session_id}/analysis")

    assert analysis.status_code == 200
    data = analysis.json()
    assert data["status"] == "win"
    assert data["agent_side"] == "p1"
    assert data["turns"] == 1
    assert data["faints_for"] == 1
    assert data["reward"] == 120.0

    profile = await client.get(
        "/api/pokemon/showdown/learning/profile",
        params={"username": "Bot", "battle_format": "vgc2024"},
    )
    assert profile.status_code == 200
    profile_data = profile.json()
    assert profile_data["battles"] >= 1
    assert profile_data["wins"] >= 1
    assert profile_data["recommendation"]["mode"] == "balanced"

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_learning_mastery_endpoint_ranks_profiles(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="api-mastery-strong",
        username="StrongBot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="balanced",
        analysis={"status": "win", "reward": 140.0, "turns": 5, "faints_for": 3, "faints_against": 0},
        decisions=[{"decision_type": "move"}],
    )
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="api-mastery-weak",
        username="WeakBot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="balanced",
        analysis={"status": "loss", "reward": 10.0, "turns": 5, "faints_for": 0, "faints_against": 3},
        decisions=[{"decision_type": "move"}],
    )

    response = await client.get(
        "/api/pokemon/showdown/learning/mastery",
        params={"battle_format": "vgc2024", "limit": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert [entry["username"] for entry in data[:2]] == ["StrongBot", "WeakBot"]
    assert data[0]["rank"] == 1
    assert data[0]["mastery_score"] > data[1]["mastery_score"]
    assert data[0]["recommendation"]["mode"] == "balanced"


@pytest.mark.asyncio
async def test_showdown_learning_mastery_endpoint_rejects_bad_limit(setup_db, client):
    response = await client.get("/api/pokemon/showdown/learning/mastery", params={"limit": 0})

    assert response.status_code == 400
    assert "limit must be between 1 and 100" in response.json()["detail"]


@pytest.mark.asyncio
async def test_showdown_session_run_once_requires_connected_socket(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/run-once", json={})

    assert response.status_code == 400
    assert "websocket is not connected" in response.json()["detail"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")
