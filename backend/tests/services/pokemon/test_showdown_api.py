"""API tests for Pokemon Showdown command and parse helpers."""

import json

import pytest

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
async def test_showdown_session_create_accepts_auto_login_without_leaking_password(client):
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
async def test_showdown_session_search_endpoint_records_commands(client):
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
async def test_showdown_session_cancel_search_endpoint_records_command(client):
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
async def test_showdown_session_accept_challenge_requires_challenger(client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/accept-challenge")

    assert response.status_code == 400
    assert "No incoming Pokemon Showdown challenge" in response.json()["detail"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_session_flush_requires_connected_socket(client):
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
async def test_showdown_session_run_once_requires_connected_socket(setup_db, client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/run-once", json={})

    assert response.status_code == 400
    assert "websocket is not connected" in response.json()["detail"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")
