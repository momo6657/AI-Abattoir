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
    random_format = next(item for item in data if item["id"] == "gen9randombattle")
    assert random_format["strategy_profile"]["archetype"] == "random_single"
    assert random_format["strategy_profile"]["target_policy"] == "no_target"


@pytest.mark.asyncio
async def test_pokemon_format_detail_resolves_alias(client):
    response = await client.get("/api/pokemon/formats/gen9vgc2024regg")

    assert response.status_code == 200
    assert response.json()["id"] == "vgc2024"


@pytest.mark.asyncio
async def test_showdown_format_capabilities_endpoint_summarizes_multi_format_support(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="format-cap-ou",
        username="MatrixBot",
        battle_format="gen9ou",
        showdown_format="gen9ou",
        mode="balanced",
        analysis={"status": "win", "reward": 140, "turns": 8, "faints_for": 3, "faints_against": 1},
        decisions=[{"decision_type": "move", "reward": 20}],
    )

    response = await client.get(
        "/api/pokemon/showdown/formats/capabilities",
        params={"username": "MatrixBot"},
    )

    assert response.status_code == 200
    data = response.json()
    formats = {item["format"]["id"]: item for item in data["formats"]}
    assert data["format_count"] >= 4
    assert data["ready_count"] == data["format_count"]
    assert formats["gen9randombattle"]["team"]["requires_team"] is False
    assert formats["gen9randombattle"]["team"]["source"] == "not_required"
    assert formats["gen9randombattle"]["strategy_profile"]["archetype"] == "random_single"
    assert formats["gen9ou"]["team"]["can_build"] is True
    assert formats["gen9ou"]["team"]["audit"]["status"] in {"passed", "warning"}
    assert "entry_hazards" in formats["gen9ou"]["team"]["audit"]["covered_priorities"]
    assert formats["gen9ou"]["battle_policy"]["target_policy"] == "no_target"
    assert formats["gen9ou"]["battle_policy"]["archetype"] == "structured_single"
    assert "entry_hazards" in formats["gen9ou"]["battle_policy"]["priorities"]
    assert formats["gen9ou"]["learning"]["battles"] == 1
    assert "research_team" in formats["gen9ou"]["recommended_actions"]


@pytest.mark.asyncio
async def test_showdown_tactical_briefing_combines_team_learning_and_plan(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="briefing-vgc-loss",
        username="BriefingBot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="defensive",
        analysis={"status": "loss", "reward": 20, "turns": 6, "faints_for": 1, "faints_against": 4},
        decisions=[{"decision_type": "move", "reward": -15}],
    )

    response = await client.get(
        "/api/pokemon/showdown/tactical-briefing",
        params={"username": "BriefingBot", "battle_format": "vgc2024", "mode": "auto"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["battle_format"] == "vgc2024"
    assert data["showdown_format"] == "gen9vgc2024regg"
    assert data["mode"] == "defensive"
    assert data["team"]["requires_team"] is True
    assert data["team"]["species"]
    assert data["team"]["preview"][0]["moves"]
    assert data["team"]["audit"]["member_count"] == len(data["team"]["species"])
    assert "fake_out_pressure" in data["team"]["audit"]["priorities"]
    assert data["learning_profile"]["battles"] == 1
    assert data["mission_recommendation"]["mission_goal"] == "prepare"
    assert "avoid_free_knockouts" in data["tactical_plan"]["priorities"]
    assert "research_team_before_ladder" in data["tactical_plan"]["risk_controls"]
    assert data["next_session_request"]["mission_goal"] == "prepare"


@pytest.mark.asyncio
async def test_showdown_tactical_briefing_handles_random_battle_without_team(setup_db, client):
    response = await client.get(
        "/api/pokemon/showdown/tactical-briefing",
        params={"username": "BriefingBot", "battle_format": "gen9randombattle", "mode": "balanced"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["team"]["requires_team"] is False
    assert data["team"]["source"] == "not_required"
    assert data["team"]["species"] == []
    assert data["tactical_plan"]["battle_type"] == "single"
    assert data["tactical_plan"]["target_policy"].startswith("No target")


@pytest.mark.asyncio
async def test_showdown_session_matchup_briefing_reads_room_preview(setup_db, client):
    session_response = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "MatchupBot", "battle_format": "vgc2024", "mode": "balanced"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]
    payload = "\n".join([
        ">battle-gen9vgc2024regg-1",
        "|player|p1|MatchupBot|",
        "|player|p2|PreviewBoss|",
        "|poke|p1|Incineroar, L50|",
        "|poke|p1|Flutter Mane, L50|",
        "|poke|p2|Tornadus, L50|",
        "|poke|p2|Amoonguss, L50|",
        "|poke|p2|Flutter Mane, L50|",
    ])
    message_response = await client.post(
        f"/api/pokemon/showdown/sessions/{session_id}/message",
        json={"payload": payload, "auto_respond": False},
    )
    assert message_response.status_code == 200

    briefing_response = await client.get(
        f"/api/pokemon/showdown/sessions/{session_id}/matchup-briefing",
        params={"include_knowledge": False},
    )

    assert briefing_response.status_code == 200
    data = briefing_response.json()
    threat_ids = {threat["id"] for threat in data["threats"]}
    assert data["room_id"] == "battle-gen9vgc2024regg-1"
    assert data["sides"]["opponent_username"] == "PreviewBoss"
    assert data["opponent"]["species"] == ["Tornadus", "Amoonguss", "Flutter Mane"]
    assert "speed_control" in threat_ids
    assert "redirection" in threat_ids
    assert "deny_or_match_speed_control" in data["matchup_plan"]["target_priority"]
    assert "protect_key_attacker_from_fake_out_turn" not in data["matchup_plan"]["risk_controls"]
    assert data["matchup_plan"]["confidence"] == "medium"


@pytest.mark.asyncio
async def test_showdown_session_matchup_briefing_requires_room_data(setup_db, client):
    session_response = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "MatchupBot", "battle_format": "gen9randombattle", "mode": "balanced"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    response = await client.get(f"/api/pokemon/showdown/sessions/{session_id}/matchup-briefing")

    assert response.status_code == 400
    assert "No Showdown battle room" in response.json()["detail"]


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
    assert created_data["team_audit"]["member_count"] == 4
    assert created_data["team_audit"]["status"] in {"passed", "warning"}
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
async def test_showdown_session_readiness_endpoint_returns_live_audit(setup_db, client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "battle_format": "gen9vgc2024regg"},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    response = await client.get(f"/api/pokemon/showdown/sessions/{session_id}/readiness")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["live_readiness"]["status"] == "action_required"
    assert data["live_readiness"]["ready_for_ladder"] is False
    assert "connect" in data["live_readiness"]["recommended_actions"]
    assert any(check["id"] == "team" and check["status"] == "ready" for check in data["live_readiness"]["checks"])

    deleted = await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_showdown_session_auto_mode_uses_policy_evaluation(setup_db, db, client):
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
    assert data["mode"] == "balanced"
    assert data["mode_source"] == "policy_evaluation"
    assert data["mode_recommendation"]["mode"] == "balanced"
    assert data["mode_recommendation"]["policy_phase"] == "explore"
    assert data["mode_recommendation"]["policy"] == "explore_under_sampled_mode"
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
    assert data["mission_goal"] == "ladder"
    assert data["mission_goal_source"] == "policy_evaluation"
    assert data["action_plan_source"] == "policy_evaluation"
    assert data["mission_request"]["mission_goal"] == "auto"
    assert data["mission_request"]["battle_format"] == "gen9randombattle"
    assert data["mission_request"]["max_actions"] == 4
    assert data["mission_request"]["max_messages"] == 12
    assert "login_password" not in data["mission_request"]
    assert data["policy_evaluation"]["phase"] == "explore"
    assert data["policy_actions"] == ["start_search", "autopilot", "analyze"]
    assert data["executable_policy_actions"] == [
        "connect",
        "flush_pending",
        "start_search",
        "autopilot",
        "analyze",
    ]
    assert data["unsupported_policy_actions"] == []
    assert data["allowed_actions"] == data["executable_policy_actions"]
    assert data["executable_plan_actions"] == [
        "connect",
        "flush_pending",
        "start_search",
        "autopilot",
        "analyze",
        "new_session",
    ]
    assert data["training_task_actions"] == ["start_search", "autopilot", "analyze", "new_session"]
    assert data["executable_task_actions"] == data["executable_plan_actions"]
    assert data["unsupported_task_actions"] == []
    assert data["training_tasks"][0]["action"] == "start_search"


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
    assert data["mission_goal_source"] == "team_audit"
    assert data["allowed_actions"] == ["research_team"]
    assert data["action_plan_source"] == "team_audit"
    assert data["team_source"] == "template"
    assert data["team_audit"]["member_count"] == len(data["team_species"])
    assert data["team_audit"]["status"] == "warning"
    assert data["team_audit_gaps"]
    assert data["team_audit_actions"] == ["research_team"]
    assert data["mission_request"]["auto_search"] is False


def test_showdown_auto_policy_uses_team_audit_before_ladder():
    payload = ShowdownSessionMissionRequest(
        username="AuditPolicyBot",
        battle_format="vgc2024",
        mission_goal="auto",
    )
    session = {
        "has_knowledge_context": False,
        "team_species": ["Incineroar", "Flutter Mane"],
        "team_audit": {
            "status": "warning",
            "score": 72,
            "gaps": ["speed_control", "redirection_support"],
            "recommendation": "The generated team should research missing support roles.",
        },
        "learning_profile": {
            "battles": 5,
            "win_rate": 0.65,
            "average_reward": 80.0,
            "training_plan": {
                "next_mission_goal": "learn",
                "actions": ["start_search", "autopilot", "analyze"],
                "reason": "Performance is strong enough to keep laddering.",
            },
        },
    }

    policy = pokemon_api._resolve_showdown_mission_policy(payload, session)

    assert policy["mission_goal"] == "prepare"
    assert policy["mission_goal_source"] == "team_audit"
    assert policy["action_plan_source"] == "team_audit"
    assert policy["allowed_actions"] == ["research_team"]
    assert policy["team_audit_gaps"] == ["speed_control", "redirection_support"]
    assert "missing support roles" in policy["mission_goal_reason"]


def test_showdown_auto_policy_uses_blocked_live_readiness_before_ladder():
    payload = ShowdownSessionMissionRequest(
        username="",
        battle_format="gen9randombattle",
        mission_goal="auto",
    )
    session = {
        "has_knowledge_context": False,
        "team_species": [],
        "live_readiness": {
            "status": "blocked",
            "score": 86,
            "recommended_actions": ["connect", "start_search"],
            "checks": [
                {
                    "id": "username",
                    "label": "Trainer name",
                    "status": "blocked",
                    "detail": "A Showdown trainer name is required.",
                    "action": None,
                },
                {
                    "id": "connection",
                    "label": "Websocket",
                    "status": "action_required",
                    "detail": "Connect to Pokemon Showdown before sending queued commands.",
                    "action": "connect",
                },
            ],
        },
        "learning_profile": {
            "battles": 6,
            "win_rate": 0.75,
            "average_reward": 100.0,
            "training_plan": {
                "next_mission_goal": "learn",
                "actions": ["start_search", "autopilot"],
            },
        },
    }

    policy = pokemon_api._resolve_showdown_mission_policy(payload, session)

    assert policy["mission_goal"] == "prepare"
    assert policy["mission_goal_source"] == "live_readiness"
    assert policy["mission_goal_reason"].startswith("A Showdown trainer name is required.")
    assert policy["action_plan_source"] == "live_readiness"
    assert policy["allowed_actions"] == ["review_readiness"]
    assert policy["readiness_status"] == "blocked"
    assert policy["readiness_actions"] == ["review_readiness"]
    assert policy["require_live_readiness"] is False


@pytest.mark.asyncio
async def test_showdown_mission_auto_reviews_blocked_live_readiness(setup_db, client):
    response = await client.post(
        "/api/pokemon/showdown/mission",
        json={
            "username": "",
            "battle_format": "gen9randombattle",
            "mission_goal": "auto",
            "max_actions": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()
    session_id = data["session"]["session_id"]
    assert data["mission_summary"]["mission_goal"] == "prepare"
    assert data["mission_summary"]["mission_goal_source"] == "live_readiness"
    assert data["mission_summary"]["action_plan_source"] == "live_readiness"
    assert data["mission_summary"]["allowed_actions"] == ["review_readiness"]
    assert data["mission_summary"]["readiness_status"] == "blocked"
    assert data["mission_summary"]["readiness_actions"] == ["review_readiness"]
    assert data["mission_summary"]["require_live_readiness"] is False
    assert data["supervisor"]["steps"][0]["action"] == "review_readiness"
    assert data["supervisor"]["steps"][0]["result"]["live_readiness"]["status"] == "blocked"

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


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
    assert [round_item["planned_goal"] for round_item in data["rounds"]] == ["ladder", "ladder"]
    assert all(round_item["planned_goal_source"] == "policy_evaluation" for round_item in data["rounds"])
    assert all(round_item["action_plan_source"] == "custom" for round_item in data["rounds"])
    assert all(round_item["recovery_action_source"]["status"] == "custom_override" for round_item in data["rounds"])
    assert all(round_item["supervisor_step_count"] == 1 for round_item in data["rounds"])
    assert all(round_item["mission_summary"]["allowed_actions"] == ["start_search"] for round_item in data["rounds"])
    assert data["progress"]["before_mastery_score"] > 0
    assert data["progress"]["after_mastery_score"] == data["mastery_score"]
    assert data["progress"]["battle_delta"] == 0
    assert data["progress"]["direction"] == "unchanged"
    assert data["recovery"]["status"] == "resume"
    assert data["training_health"]["status"] == "recovering"
    assert data["training_health"]["next_intervention"] == "resume_recovery"
    assert "connect" in data["training_health"]["priority_actions"]
    assert data["next_training_chain"]["intervention"] == "resume_recovery"
    assert data["next_training_chain"]["can_auto_continue"] is True
    assert data["next_training_chain"]["request"]["rounds"] == 1
    assert "connect" in data["next_training_chain"]["request"]["allowed_actions"]
    assert "login_password" not in data["next_training_chain"]["request"]
    assert data["recovery"]["action_counts"]["connect"] == 8
    assert data["recovery"]["action_counts"]["autopilot"] == 4
    assert data["recovery"]["policy_count"] == 6
    assert data["recovery"]["rounds"][-1]["status"] == "resume"
    assert data["training_chain_summary"]["chain_number"] == 1
    assert data["training_chain_summary"]["completed_rounds"] == 2
    assert data["training_chain_summary"]["progress"]["after_mastery_score"] == data["mastery_score"]
    assert data["training_chain_summary"]["recovery"]["actions"][0] == "connect"
    assert data["training_chain_summary"]["recovery"]["policy_count"] == 6
    assert data["training_chain_summary"]["training_health"]["next_intervention"] == "resume_recovery"
    assert data["training_chain_summary"]["next_training_chain"]["request"]["rounds"] == 1
    assert data["training_chain_summary"]["rounds"][-1]["planned_goal"] == "ladder"
    assert data["training_chain_summary"]["rounds"][-1]["recovery_status"] == "resume"
    assert data["final_session"]["last_training_chain_summary"]["completed_rounds"] == 2
    assert data["final_session"]["last_training_chain_summary"]["recovery"]["status"] == "resume"
    assert data["final_session"]["last_training_chain_summary"]["training_health"]["status"] == "recovering"
    assert data["final_session"]["last_training_chain_summary"]["next_training_chain"]["intervention"] == "resume_recovery"
    assert data["final_session"]["training_chain_history_count"] == 1
    assert data["final_session"]["training_chain_trend"]["chain_count"] == 1
    assert data["final_session"]["training_chain_trend"]["direction"] in {"flat", "improving"}

    for round_item in data["rounds"]:
        await client.delete(f"/api/pokemon/showdown/sessions/{round_item['session_id']}")


@pytest.mark.asyncio
async def test_showdown_training_chain_applies_previous_recovery_actions(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="chain-recovery-win",
        username="RecoveryBot",
        battle_format="gen9randombattle",
        showdown_format="gen9randombattle",
        mode="aggressive",
        analysis={"status": "win", "reward": 130.0, "turns": 4, "faints_for": 3, "faints_against": 0},
        decisions=[{"decision_type": "move"}],
    )

    response = await client.post(
        "/api/pokemon/showdown/training-chain",
        json={
            "username": "RecoveryBot",
            "battle_format": "gen9randombattle",
            "mode": "auto",
            "mission_goal": "auto",
            "rounds": 2,
            "max_actions": 1,
            "stop_on_finished": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["completed_rounds"] == 2
    assert data["rounds"][0]["recovery_action_source"]["status"] == "none"
    assert data["rounds"][1]["recovery_action_source"]["status"] == "applied"
    assert data["rounds"][1]["recovery_action_source"]["source"] == "previous_round_recovery"
    assert data["rounds"][1]["planned_actions"] == data["rounds"][0]["recovery"]["actions"]
    assert data["rounds"][1]["mission_summary"]["allowed_actions"] == data["rounds"][0]["recovery"]["actions"]
    assert data["rounds"][1]["recovery_effectiveness"]["applied_count"] == len(data["rounds"][0]["recovery"]["actions"])
    assert data["rounds"][1]["recovery_effectiveness"]["status"] in {"partial", "stuck", "shifted", "cleared"}
    assert data["recovery_effectiveness"]["applied_rounds"] == 1
    assert data["training_chain_summary"]["recovery_effectiveness"]["applied_rounds"] == 1
    assert data["training_chain_summary"]["rounds"][1]["recovery_action_source"]["status"] == "applied"
    assert data["training_chain_summary"]["rounds"][1]["recovery_effectiveness"]["applied_count"] == len(data["rounds"][0]["recovery"]["actions"])

    for round_item in data["rounds"]:
        await client.delete(f"/api/pokemon/showdown/sessions/{round_item['session_id']}")


@pytest.mark.asyncio
async def test_showdown_training_loop_continues_from_next_chain_preset(setup_db, db, monkeypatch):
    calls = []

    async def fake_training_chain(payload, chain_db):
        calls.append(payload)
        chain_index = len(calls)
        next_request = (
            {
                "username": payload.username,
                "battle_format": payload.battle_format,
                "mode": payload.mode,
                "mission_goal": "auto",
                "rounds": 1,
                "max_actions": 1,
                "allowed_actions": ["analyze"],
                "send_commands": False,
                "stop_on_finished": False,
            }
            if chain_index == 1
            else None
        )
        return {
            "requested_rounds": payload.rounds,
            "completed_rounds": 1,
            "stop_reason": "round_limit",
            "mastery_score": 12.5 * chain_index,
            "progress": {"direction": "improved"},
            "recovery": {"status": "clear", "actions": []},
            "recovery_effectiveness": {"status": "cleared"},
            "training_health": {
                "status": "healthy" if chain_index == 1 else "blocked",
                "next_intervention": "continue_chain" if chain_index == 1 else "review_blockers",
                "recommendation": "Continue bounded loop." if chain_index == 1 else "Review blocker before continuing.",
            },
            "next_training_chain": {
                "intervention": "continue_chain" if chain_index == 1 else "review_blockers",
                "can_auto_continue": chain_index == 1,
                "request": next_request,
            },
            "training_chain_summary": {"chain_index": chain_index},
            "final_session": {
                "session_id": f"loop-{chain_index}",
                "battle_format": payload.battle_format,
            },
        }

    monkeypatch.setattr(pokemon_api, "run_showdown_training_chain", fake_training_chain)

    data = await pokemon_api.run_showdown_training_loop(
        pokemon_api.ShowdownTrainingLoopRequest(
            username="LoopBot",
            battle_format="gen9randombattle",
            mode="auto",
            mission_goal="auto",
            rounds=1,
            chain_limit=3,
            max_actions=1,
            allowed_actions=["start_search"],
            login_password="secret",
            send_commands=False,
            stop_on_finished=False,
        ),
        db,
    )

    assert len(calls) == 2
    assert calls[0].allowed_actions == ["start_search"]
    assert calls[0].login_password == "secret"
    assert calls[1].allowed_actions == ["analyze"]
    assert calls[1].login_password is None
    assert data["requested_chain_limit"] == 3
    assert data["completed_chains"] == 2
    assert data["total_completed_rounds"] == 2
    assert data["stop_reason"] == "blocked_intervention"
    assert data["chains"][0]["loop_index"] == 1
    assert data["chains"][1]["loop_index"] == 2
    assert data["chains"][0]["next_training_chain"]["request"]
    assert data["final_training_health"]["next_intervention"] == "review_blockers"


@pytest.mark.asyncio
async def test_showdown_training_loop_rejects_invalid_chain_limit(setup_db, client):
    response = await client.post(
        "/api/pokemon/showdown/training-loop",
        json={
            "username": "LoopBot",
            "battle_format": "gen9randombattle",
            "rounds": 1,
            "chain_limit": 0,
        },
    )

    assert response.status_code == 400
    assert "chain_limit must be between 1 and 6" in response.json()["detail"]


@pytest.mark.asyncio
async def test_showdown_training_program_rotates_across_formats(setup_db, db, monkeypatch):
    calls = []

    async def fake_training_loop(payload, loop_db):
        calls.append(payload)
        index = len(calls)
        return {
            "username": payload.username,
            "battle_format": payload.battle_format,
            "requested_chain_limit": payload.chain_limit,
            "completed_chains": payload.chain_limit,
            "total_completed_rounds": payload.chain_limit,
            "stop_reason": "chain_limit",
            "final_session": {"session_id": f"program-{index}", "battle_format": payload.battle_format},
            "final_mastery_score": 100.0 + index,
            "final_progress": {"direction": "improved"},
            "final_training_health": {"status": "healthy", "next_intervention": "continue_chain"},
            "next_training_chain": {
                "intervention": "continue_chain",
                "can_auto_continue": True,
                "request": {"username": payload.username, "battle_format": payload.battle_format},
            },
            "chains": [],
        }

    monkeypatch.setattr(pokemon_api, "run_showdown_training_loop", fake_training_loop)

    data = await pokemon_api.run_showdown_training_program(
        pokemon_api.ShowdownTrainingProgramRequest(
            username="ProgramBot",
            battle_format="gen9randombattle",
            formats=["gen9randombattle", "gen9ou"],
            format_limit=2,
            chain_limit=2,
            rounds=1,
            login_password="secret",
            send_commands=False,
        ),
        db,
    )

    assert [call.battle_format for call in calls] == ["gen9randombattle", "gen9ou"]
    assert data["completed_formats"] == 2
    assert data["evaluated_formats"] == 2
    assert data["skipped_formats"] == 0
    assert data["total_completed_chains"] == 4
    assert data["total_completed_rounds"] == 4
    assert data["stop_reason"] == "format_limit"
    assert data["formats"][0]["format"]["id"] == "gen9randombattle"
    assert data["formats"][1]["format"]["id"] == "gen9ou"
    assert data["formats"][0]["preflight_status"] in {"ready", "watch", "blocked"}
    assert data["formats"][0]["mission_preview"]["mission_goal"]
    assert data["program_health"]["status"] == "training"
    assert data["program_health"]["priority_formats"] == ["gen9randombattle", "gen9ou"]
    assert data["program_health"]["trained_format_count"] == 2
    assert data["next_training_program"]["can_auto_continue"] is True
    assert data["next_training_program"]["can_auto_recover"] is False
    assert data["next_training_program"]["can_resume_after_recovery"] is False
    assert data["next_training_program"]["request"]["formats"] == ["gen9randombattle", "gen9ou"]
    assert "login_password" not in data["next_training_program"]["request"]


@pytest.mark.asyncio
async def test_showdown_training_program_stops_on_preflight_blocked(setup_db, db, monkeypatch):
    calls = []

    async def fake_training_loop(payload, loop_db):
        calls.append(payload)
        return {"stop_reason": "chain_limit"}

    async def fake_attach_previews(payload, curriculum, preview_db):
        return [
            {
                **item,
                "mission_preview": {
                    "mission_goal": "ladder",
                    "allowed_actions": ["connect"],
                    "readiness_status": "blocked",
                    "team_audit_status": "ready",
                    "unsupported_plan_actions": [],
                    "unsupported_task_actions": [],
                    "unsupported_policy_actions": [],
                    "training_task_count": 0,
                },
            }
            for item in curriculum
        ]

    monkeypatch.setattr(pokemon_api, "run_showdown_training_loop", fake_training_loop)
    monkeypatch.setattr(pokemon_api, "_attach_showdown_training_program_mission_previews", fake_attach_previews)

    data = await pokemon_api.run_showdown_training_program(
        pokemon_api.ShowdownTrainingProgramRequest(
            username="ProgramBlockedBot",
            battle_format="gen9randombattle",
            formats=["gen9randombattle"],
            format_limit=1,
            chain_limit=2,
            rounds=1,
            stop_on_blocked=True,
            send_commands=False,
        ),
        db,
    )

    assert calls == []
    assert data["stop_reason"] == "preflight_blocked"
    assert data["evaluated_formats"] == 1
    assert data["completed_formats"] == 0
    assert data["skipped_formats"] == 1
    assert data["formats"][0]["skipped"] is True
    assert data["formats"][0]["preflight_status"] == "blocked"
    assert data["formats"][0]["preflight_blockers"] == ["live_readiness"]
    assert data["program_health"]["status"] == "blocked"
    assert data["program_health"]["manual_review_required"] is True
    assert data["program_health"]["blocked_formats"] == ["gen9randombattle"]
    assert data["program_health"]["trained_format_count"] == 0
    assert data["program_health"]["skipped_format_count"] == 1
    assert data["program_health"]["recovery_formats"] == ["gen9randombattle"]
    assert data["program_health"]["recovery_actions"] == ["connect"]
    assert data["next_training_program"]["can_auto_continue"] is False
    assert data["next_training_program"]["can_auto_recover"] is True
    assert data["next_training_program"]["can_resume_after_recovery"] is True
    assert data["next_training_program"]["recovery_formats"] == ["gen9randombattle"]
    assert data["next_training_program"]["recovery_actions"] == ["connect"]
    assert data["next_training_program"]["recovery_request"]["formats"] == ["gen9randombattle"]
    assert data["next_training_program"]["recovery_request"]["battle_format"] == "gen9randombattle"
    assert data["next_training_program"]["recovery_request"]["chain_limit"] == 1
    assert data["next_training_program"]["recovery_request"]["rounds"] == 1
    assert data["next_training_program"]["recovery_request"]["allowed_actions"] == ["connect"]
    assert data["next_training_program"]["recovery_request"]["stop_on_blocked"] is False
    assert "login_password" not in data["next_training_program"]["recovery_request"]
    assert data["next_training_program"]["after_recovery_formats"] == ["gen9randombattle"]
    assert data["next_training_program"]["after_recovery_request"]["formats"] == ["gen9randombattle"]
    assert data["next_training_program"]["after_recovery_request"]["battle_format"] == "gen9randombattle"
    assert data["next_training_program"]["after_recovery_request"]["stop_on_blocked"] is True
    assert "login_password" not in data["next_training_program"]["after_recovery_request"]


@pytest.mark.asyncio
async def test_showdown_training_program_pipeline_recovers_and_resumes(setup_db, db, monkeypatch):
    calls = []

    async def fake_training_program(payload, program_db):
        calls.append(payload)
        if len(calls) == 1:
            return {
                "stop_reason": "preflight_blocked",
                "program_health": {
                    "status": "blocked",
                    "manual_review_required": True,
                    "recommendation": "recover first",
                },
                "next_training_program": {
                    "can_auto_continue": False,
                    "can_auto_recover": True,
                    "can_resume_after_recovery": True,
                    "recovery_request": {
                        "username": payload.username,
                        "battle_format": "gen9randombattle",
                        "formats": ["gen9randombattle"],
                        "format_limit": 1,
                        "chain_limit": 1,
                        "rounds": 1,
                        "mission_goal": "auto",
                        "allowed_actions": ["connect"],
                        "stop_on_blocked": False,
                    },
                    "after_recovery_request": {
                        "username": payload.username,
                        "battle_format": "gen9randombattle",
                        "formats": ["gen9randombattle", "gen9ou"],
                        "format_limit": 2,
                        "chain_limit": 2,
                        "rounds": 1,
                        "stop_on_blocked": True,
                    },
                },
            }
        return {
            "stop_reason": "format_limit",
            "program_health": {
                "status": "training",
                "manual_review_required": False,
                "recommendation": "continue",
            },
            "next_training_program": {},
        }

    monkeypatch.setattr(pokemon_api, "run_showdown_training_program", fake_training_program)

    data = await pokemon_api.run_showdown_training_program_pipeline(
        pokemon_api.ShowdownTrainingProgramPipelineRequest(
            username="PipelineBot",
            battle_format="gen9randombattle",
            formats=["gen9randombattle", "gen9ou"],
            format_limit=2,
            chain_limit=2,
            rounds=1,
            stage_limit=3,
            login_password="secret",
            send_commands=False,
        ),
        db,
    )

    assert [call.battle_format for call in calls] == ["gen9randombattle", "gen9randombattle", "gen9randombattle"]
    assert calls[1].allowed_actions == ["connect"]
    assert calls[1].stop_on_blocked is False
    assert calls[2].formats == ["gen9randombattle", "gen9ou"]
    assert calls[2].stop_on_blocked is True
    assert data["completed_stages"] == 3
    assert data["stop_reason"] == "no_next_stage"
    assert data["stage_types"] == ["program", "recovery", "after_recovery"]
    assert data["pipeline_health"]["status"] == "resumed"
    assert data["pipeline_health"]["recovered"] is True
    assert data["pipeline_health"]["resumed_after_recovery"] is True
    assert data["autonomous_trace"][0]["decision"]["action"] == "auto_recover"
    assert data["autonomous_trace"][1]["decision"]["action"] == "auto_resume_after_recovery"
    assert data["autonomous_trace"][2]["decision"]["action"] == "complete"
    assert data["next_action"]["type"] == "complete"
    assert data["next_action"]["requires_operator"] is False
    assert "login_password" not in data["stages"][0]["request"]
    assert data["final_result"]["program_health"]["status"] == "training"


@pytest.mark.asyncio
async def test_showdown_training_program_autopilot_consumes_next_action(setup_db, db, monkeypatch):
    calls = []

    async def fake_pipeline(payload, pipeline_db):
        calls.append(payload)
        if len(calls) == 1:
            return {
                "completed_stages": 1,
                "stage_types": ["program"],
                "final_result": {"total_completed_rounds": 2},
                "next_action": {
                    "type": "run_next_program",
                    "label": "continue",
                    "requires_operator": False,
                    "request": {
                        "username": payload.username,
                        "battle_format": "gen9ou",
                        "formats": ["gen9ou"],
                        "format_limit": 1,
                        "chain_limit": 1,
                        "rounds": 1,
                        "login_password": "secret",
                    },
                },
            }
        return {
            "completed_stages": 2,
            "stage_types": ["program", "after_recovery"],
            "final_result": {"total_completed_rounds": 3},
            "next_action": {
                "type": "complete",
                "label": "done",
                "requires_operator": False,
                "request": None,
            },
        }

    monkeypatch.setattr(pokemon_api, "run_showdown_training_program_pipeline", fake_pipeline)

    data = await pokemon_api.run_showdown_training_program_autopilot(
        pokemon_api.ShowdownTrainingProgramAutopilotRequest(
            username="AutopilotBot",
            battle_format="gen9randombattle",
            formats=["gen9randombattle", "gen9ou"],
            format_limit=2,
            chain_limit=2,
            rounds=1,
            stage_limit=3,
            cycle_limit=3,
            login_password="secret",
            send_commands=False,
        ),
        db,
    )

    assert [call.battle_format for call in calls] == ["gen9randombattle", "gen9ou"]
    assert calls[1].formats == ["gen9ou"]
    assert calls[1].stage_limit == 3
    assert data["completed_cycles"] == 2
    assert data["stop_reason"] == "complete"
    assert data["autopilot_health"]["status"] == "complete"
    assert data["autopilot_health"]["total_stages"] == 3
    assert data["autopilot_health"]["total_completed_rounds"] == 5
    assert data["autopilot_health"]["stage_types"] == ["program", "program", "after_recovery"]
    assert "login_password" not in data["cycles"][0]["request"]
    assert "login_password" not in data["cycles"][1]["request"]


@pytest.mark.asyncio
async def test_showdown_training_program_plan_builds_safe_curriculum(setup_db, db, client):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="program-plan-ou",
        username="ProgramPlanBot",
        battle_format="gen9ou",
        showdown_format="gen9ou",
        mode="balanced",
        analysis={"status": "win", "reward": 120.0, "turns": 8, "faints_for": 3, "faints_against": 1},
        decisions=[{"decision_type": "move", "reward": 20}],
    )

    response = await client.post(
        "/api/pokemon/showdown/training-program/plan",
        json={
            "username": "ProgramPlanBot",
            "battle_format": "gen9randombattle",
            "formats": ["gen9randombattle", "gen9ou", "gen9ou"],
            "format_limit": 3,
            "chain_limit": 2,
            "rounds": 1,
            "login_password": "secret",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["planned_format_count"] == 2
    assert data["priority_formats"] == ["gen9randombattle", "gen9ou"]
    assert data["status"] == "needs_samples"
    assert data["no_sample_formats"] == ["gen9randombattle"]
    assert data["total_existing_samples"] == 1
    assert data["program_request"]["formats"] == ["gen9randombattle", "gen9ou"]
    assert data["program_request"]["battle_format"] == "gen9randombattle"
    assert data["program_request"]["chain_limit"] == 2
    assert "login_password" not in data["program_request"]
    assert data["preview_status"] in {"ready", "watch", "blocked"}
    assert isinstance(data["high_risk_formats"], list)
    assert isinstance(data["executable_action_count"], int)
    assert data["training_task_count"] >= 0
    assert [item["format"]["id"] for item in data["curriculum"]] == ["gen9randombattle", "gen9ou"]
    assert all(item["mission_preview"]["mission_goal"] for item in data["curriculum"])
    assert data["curriculum"][0]["mission_preview"]["allowed_actions"]
    assert "login_password" not in data["curriculum"][0]["mission_preview"]


@pytest.mark.asyncio
async def test_showdown_training_program_rejects_invalid_format_limit(setup_db, client):
    response = await client.post(
        "/api/pokemon/showdown/training-program",
        json={
            "username": "ProgramBot",
            "battle_format": "gen9randombattle",
            "rounds": 1,
            "format_limit": 0,
        },
    )

    assert response.status_code == 400
    assert "format_limit must be between 1 and 4" in response.json()["detail"]


@pytest.mark.asyncio
async def test_showdown_training_chain_resumes_recovery_from_previous_chain(setup_db, client):
    previous = pokemon_api.pokemon_showdown_session_service.create_session(
        username="CarryBot",
        team=None,
        battle_format="gen9randombattle",
    )
    pokemon_api.pokemon_showdown_session_service.store_training_chain_summary(
        previous.session_id,
        {
            "username": "CarryBot",
            "battle_format": "gen9randombattle",
            "showdown_format": "gen9randombattle",
            "requested_rounds": 2,
            "completed_rounds": 2,
            "stop_reason": "round_limit",
            "mastery_score": 10,
            "progress": {"direction": "unchanged", "battle_delta": 0},
            "recovery": {
                "status": "resume",
                "actions": ["analyze"],
                "action_counts": {"analyze": 1},
                "task_count": 1,
                "rounds": [{"round": 2, "status": "resume", "actions": ["analyze"], "task_count": 1}],
                "blocked_reasons": [],
                "recommendation": "Resume analysis.",
            },
            "rounds": [],
        },
    )

    response = await client.post(
        "/api/pokemon/showdown/training-chain",
        json={
            "username": "CarryBot",
            "battle_format": "gen9randombattle",
            "mode": "auto",
            "mission_goal": "auto",
            "rounds": 1,
            "max_actions": 1,
            "send_commands": False,
            "stop_on_finished": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["initial_recovery"]["actions"] == ["analyze"]
    assert data["initial_recovery"]["chain_number"] == 1
    assert data["rounds"][0]["recovery_action_source"]["status"] == "applied"
    assert data["rounds"][0]["recovery_action_source"]["source"] == "previous_training_chain_recovery"
    assert data["rounds"][0]["planned_actions"] == ["analyze"]
    assert data["rounds"][0]["mission_summary"]["allowed_actions"] == ["analyze"]
    assert data["training_chain_summary"]["initial_recovery"]["actions"] == ["analyze"]

    await client.delete(f"/api/pokemon/showdown/sessions/{previous.session_id}")
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
    assert data["mission_summary"]["mission_goal_source"] == "team_audit"
    assert data["mission_summary"]["allowed_actions"] == ["research_team"]
    assert data["mission_summary"]["team_audit"]["status"] == "warning"
    assert data["mission_summary"]["team_audit_actions"] == ["research_team"]
    assert data["mission_summary"]["training_plan"]["stage"] == "collect_data"
    assert data["mission_summary"]["training_plan"]["next_mission_goal"] == "queue"
    assert data["session"]["last_mission_summary"]["mission_goal"] == "prepare"
    assert data["session"]["has_knowledge_context"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")


@pytest.mark.asyncio
async def test_showdown_mission_auto_goal_uses_policy_evaluation(setup_db, db, client):
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
    assert data["mission_summary"]["mission_goal"] == "ladder"
    assert data["mission_summary"]["mission_goal_source"] == "policy_evaluation"
    assert data["mission_summary"]["action_plan_source"] == "custom"
    assert data["mission_summary"]["policy_evaluation"]["phase"] == "explore"
    assert data["mission_summary"]["policy_actions"] == ["start_search", "autopilot", "analyze"]
    assert data["mission_summary"]["policy_status"] == "partial"
    assert data["mission_summary"]["policy_progress"]["executed_actions"] == ["start_search"]
    assert data["mission_summary"]["policy_progress"]["tasks"][0]["status"] == "partial"
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
    assert data["mission_summary"]["training_task_status"] == "partial"
    assert data["mission_summary"]["training_task_partial_count"] == 2
    assert data["mission_summary"]["training_task_pending_count"] >= 1
    progress = data["mission_summary"]["training_task_progress"]
    assert progress["executed_actions"] == ["start_search"]
    tasks_by_action = {task["action"]: task for task in progress["tasks"]}
    assert tasks_by_action["start_search"]["status"] == "partial"
    assert "connect" in tasks_by_action["start_search"]["missing_actions"]
    assert tasks_by_action["autopilot"]["status"] == "partial"
    assert "autopilot" in tasks_by_action["autopilot"]["missing_actions"]
    assert data["session"]["last_mission_summary"]["mission_goal_source"] == "policy_evaluation"
    assert data["session"]["last_mission_summary"]["policy_status"] == "partial"
    assert data["session"]["last_mission_summary"]["training_task_status"] == "partial"

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


def test_showdown_auto_policy_evaluation_overrides_training_plan_goal():
    payload = ShowdownSessionMissionRequest(
        username="PolicyEvalBot",
        battle_format="gen9randombattle",
        mission_goal="auto",
    )
    session = {
        "has_knowledge_context": False,
        "team_species": [],
        "learning_profile": {
            "battles": 1,
            "win_rate": 1.0,
            "average_reward": 125.0,
            "training_plan": {
                "next_mission_goal": "learn",
                "actions": ["start_search", "autopilot", "analyze", "new_session"],
            },
            "policy_evaluation": {
                "phase": "explore",
                "policy": "explore_under_sampled_mode",
                "recommended_mode": "balanced",
                "confidence": "low",
                "risk": "low",
                "next_experiment": {
                    "mode": "balanced",
                    "mission_goal": "ladder",
                    "reason": "balanced needs more samples before exploiting.",
                },
            },
        },
    }

    policy = pokemon_api._resolve_showdown_mission_policy(payload, session)

    assert policy["mission_goal"] == "ladder"
    assert policy["mission_goal_source"] == "policy_evaluation"
    assert policy["mission_goal_reason"] == "balanced needs more samples before exploiting."
    assert policy["action_plan_source"] == "policy_evaluation"
    assert policy["policy_actions"] == ["start_search", "autopilot", "analyze"]
    assert policy["allowed_actions"] == ["connect", "flush_pending", "start_search", "autopilot", "analyze"]
    assert policy["unsupported_policy_actions"] == []


def test_showdown_auto_policy_prefers_executable_training_tasks():
    payload = ShowdownSessionMissionRequest(
        username="TaskPolicyBot",
        battle_format="gen9randombattle",
        mission_goal="auto",
    )
    session = {
        "has_knowledge_context": False,
        "team_species": [],
        "learning_profile": {
            "battles": 4,
            "win_rate": 0.7,
            "average_reward": 90.0,
            "training_plan": {
                "next_mission_goal": "learn",
                "actions": ["start_search", "autopilot", "analyze"],
                "reason": "Use task evidence to drive the next learning loop.",
            },
            "training_tasks": [
                {
                    "id": "normal-search",
                    "action": "start_search",
                    "priority": "normal",
                    "stage": "exploit",
                    "evidence": "Queue another sample.",
                },
                {
                    "id": "high-audit",
                    "action": "audit_switch",
                    "priority": "high",
                    "stage": "exploit",
                    "evidence": "Switch choices need review.",
                },
            ],
        },
    }

    policy = pokemon_api._resolve_showdown_mission_policy(payload, session)

    assert policy["mission_goal"] == "learn"
    assert policy["mission_goal_source"] == "training_plan"
    assert policy["action_plan_source"] == "training_tasks"
    assert policy["training_task_actions"] == ["audit_switch", "start_search"]
    assert policy["allowed_actions"] == ["analyze", "connect", "flush_pending", "start_search"]
    assert policy["executable_task_actions"] == ["analyze", "connect", "flush_pending", "start_search"]
    assert policy["unsupported_task_actions"] == []
    assert policy["training_tasks"][0]["id"] == "high-audit"


def test_showdown_training_task_progress_tracks_completed_partial_and_pending_tasks():
    progress = pokemon_api._build_showdown_training_task_progress(
        [
            {"id": "audit", "action": "audit_switch", "priority": "high"},
            {"id": "search", "action": "start_search", "priority": "normal"},
            {"id": "custom", "action": "unmapped_action", "priority": "normal"},
        ],
        [
            {"action": "analyze"},
            {"action": "start_search"},
        ],
        stop_reason="max_actions",
    )

    assert progress["status"] == "partial"
    assert progress["completed_count"] == 1
    assert progress["partial_count"] == 1
    assert progress["unsupported_count"] == 1
    by_id = {task["id"]: task for task in progress["tasks"]}
    assert by_id["audit"]["status"] == "completed"
    assert by_id["search"]["status"] == "partial"
    assert by_id["search"]["executed_actions"] == ["start_search"]
    assert by_id["search"]["missing_actions"] == ["connect", "flush_pending"]
    assert by_id["custom"]["status"] == "unsupported"


def test_showdown_policy_action_progress_tracks_partial_policy_actions():
    progress = pokemon_api._build_showdown_policy_action_progress(
        ["start_search", "autopilot", "analyze"],
        [{"action": "start_search"}],
        stop_reason="max_actions",
    )

    assert progress["status"] == "partial"
    assert progress["completed_count"] == 0
    assert progress["partial_count"] == 2
    assert progress["pending_count"] == 1
    assert progress["executed_actions"] == ["start_search"]
    tasks_by_action = {task["action"]: task for task in progress["tasks"]}
    assert tasks_by_action["start_search"]["missing_actions"] == ["connect", "flush_pending"]
    assert tasks_by_action["autopilot"]["status"] == "partial"
    assert "autopilot" in tasks_by_action["autopilot"]["missing_actions"]
    assert tasks_by_action["analyze"]["status"] == "pending"


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


def test_showdown_training_chain_recovery_aggregates_missing_task_actions():
    rounds = [
        {
            "round": 1,
            "mission_summary": {
                "training_task_progress": {
                    "tasks": [
                        {
                            "id": "search",
                            "action": "start_search",
                            "status": "partial",
                            "missing_actions": ["connect", "flush_pending"],
                            "blocked_reason": "Mission stopped with max_actions.",
                        },
                        {
                            "id": "audit",
                            "action": "audit_switch",
                            "status": "completed",
                            "missing_actions": [],
                        },
                    ]
                }
            },
        },
        {
            "round": 2,
            "mission_summary": {
                "training_task_progress": {
                    "tasks": [
                        {
                            "id": "auto",
                            "action": "autopilot",
                            "status": "partial",
                            "missing_actions": ["connect", "flush_pending", "autopilot"],
                        },
                        {
                            "id": "custom",
                            "action": "custom_step",
                            "status": "unsupported",
                            "unsupported_actions": ["custom_step"],
                        },
                    ]
                }
            },
        },
    ]

    recovery = pokemon_api._build_showdown_training_chain_recovery(rounds)

    assert recovery["status"] == "resume"
    assert recovery["actions"] == ["connect", "flush_pending", "autopilot"]
    assert recovery["action_counts"]["connect"] == 2
    assert recovery["task_count"] == 3
    assert recovery["rounds"][0]["round"] == 1
    assert set(recovery["rounds"][1]["actions"]) == {"connect", "flush_pending", "autopilot"}
    assert "max_actions" in recovery["blocked_reasons"][0]


def test_showdown_round_recovery_includes_policy_progress_actions():
    recovery = pokemon_api._build_showdown_round_recovery(
        {
            "round": 1,
            "mission_summary": {
                "policy_progress": {
                    "tasks": [
                        {
                            "id": "policy_1_start_search",
                            "action": "start_search",
                            "status": "partial",
                            "priority": "normal",
                            "missing_actions": ["connect", "flush_pending"],
                            "unsupported_actions": [],
                            "blocked_reason": "Mission stopped with max_actions.",
                        },
                        {
                            "id": "policy_2_autopilot",
                            "action": "autopilot",
                            "status": "pending",
                            "priority": "normal",
                            "missing_actions": ["connect", "flush_pending", "start_search", "autopilot"],
                            "unsupported_actions": [],
                            "blocked_reason": "Mission stopped with max_actions.",
                        },
                    ],
                },
            },
        }
    )

    assert recovery["status"] == "resume"
    assert recovery["policy_count"] == 2
    assert recovery["task_count"] == 0
    assert recovery["action_counts"]["connect"] == 2
    assert recovery["actions"][0] == "connect"
    assert {task["source"] for task in recovery["tasks"]} == {"policy"}


def test_showdown_recovery_effectiveness_marks_cleared_actions():
    effect = pokemon_api._build_showdown_recovery_effectiveness(
        {"status": "applied", "source": "previous_round_recovery", "actions": ["connect", "flush_pending"]},
        {"status": "clear", "actions": []},
    )

    assert effect["status"] == "cleared"
    assert effect["recovered_actions"] == ["connect", "flush_pending"]
    assert effect["still_pending_actions"] == []
    assert effect["burndown_ratio"] == 1.0


def test_showdown_recovery_effectiveness_marks_stuck_actions():
    effect = pokemon_api._build_showdown_recovery_effectiveness(
        {"status": "applied", "source": "previous_round_recovery", "actions": ["connect", "autopilot"]},
        {"status": "resume", "actions": ["connect", "autopilot", "analyze"]},
    )

    assert effect["status"] == "stuck"
    assert effect["still_pending_actions"] == ["connect", "autopilot"]
    assert effect["new_actions"] == ["analyze"]
    assert effect["burndown_ratio"] == 0.0


def test_showdown_training_chain_recovery_effectiveness_summarizes_rounds():
    summary = pokemon_api._build_showdown_training_chain_recovery_effectiveness(
        [
            {
                "round": 1,
                "recovery_effectiveness": {
                    "status": "not_applied",
                    "applied_count": 0,
                    "recovered_count": 0,
                    "still_pending_count": 0,
                    "new_count": 0,
                    "applied_actions": [],
                    "recovered_actions": [],
                    "still_pending_actions": [],
                    "new_actions": [],
                },
            },
            {
                "round": 2,
                "recovery_effectiveness": {
                    "status": "partial",
                    "applied_count": 3,
                    "recovered_count": 2,
                    "still_pending_count": 1,
                    "new_count": 1,
                    "applied_actions": ["connect", "flush_pending", "autopilot"],
                    "recovered_actions": ["connect", "flush_pending"],
                    "still_pending_actions": ["autopilot"],
                    "new_actions": ["analyze"],
                },
            },
        ]
    )

    assert summary["status"] == "partial"
    assert summary["applied_rounds"] == 1
    assert summary["applied_count"] == 3
    assert summary["recovered_count"] == 2
    assert summary["still_pending_count"] == 1
    assert summary["new_count"] == 1
    assert summary["burndown_ratio"] == 0.67
    assert summary["action_counts"]["recovered"]["connect"] == 1
    assert summary["still_pending_actions"] == ["autopilot"]


def test_showdown_training_chain_health_recommends_recovery_resume():
    health = pokemon_api._build_showdown_training_chain_health(
        progress={"direction": "unchanged", "battle_delta": 0},
        recovery={"status": "resume", "actions": ["connect", "autopilot"]},
        recovery_effectiveness={"status": "none", "still_pending_actions": []},
        rounds=[{"round": 1}],
    )

    assert health["status"] == "recovering"
    assert health["next_intervention"] == "resume_recovery"
    assert health["risk"] == "medium"
    assert health["priority_actions"] == ["connect", "autopilot"]
    assert "recovery:resume" in health["signals"]


def test_showdown_training_chain_health_prioritizes_stuck_recovery():
    health = pokemon_api._build_showdown_training_chain_health(
        progress={"direction": "unchanged", "battle_delta": 0},
        recovery={"status": "resume", "actions": ["connect", "autopilot"]},
        recovery_effectiveness={
            "status": "stuck",
            "stuck_rounds": 1,
            "still_pending_actions": ["autopilot"],
        },
        rounds=[{"round": 1}, {"round": 2}],
    )

    assert health["status"] == "stuck"
    assert health["next_intervention"] == "expand_recovery"
    assert health["risk"] == "high"
    assert health["priority_actions"][0] == "autopilot"
    assert "stuck_rounds:1" in health["signals"]


def test_showdown_next_training_chain_builds_live_sample_request():
    payload = pokemon_api.ShowdownTrainingChainRequest(
        username="NextBot",
        battle_format="gen9randombattle",
        mode="auto",
        mission_goal="auto",
        rounds=5,
        max_actions=2,
        login_password="secret",
    )
    format_info = pokemon_api.pokemon_format_catalog.get("gen9randombattle")

    next_chain = pokemon_api._build_showdown_next_training_chain(
        payload=payload,
        format_info=format_info,
        training_health={
            "next_intervention": "run_live_battle",
            "priority_actions": ["connect", "start_search", "autopilot"],
            "recommendation": "Run a live battle.",
        },
    )

    assert next_chain["can_auto_continue"] is True
    assert next_chain["intervention"] == "run_live_battle"
    assert next_chain["request"]["mission_goal"] == "ladder"
    assert next_chain["request"]["rounds"] == 3
    assert next_chain["request"]["max_actions"] == 3
    assert next_chain["request"]["allowed_actions"] == ["connect", "start_search", "autopilot"]
    assert "login_password" not in next_chain["request"]


def test_showdown_next_training_chain_blocks_review_request():
    payload = pokemon_api.ShowdownTrainingChainRequest(
        username="BlockedBot",
        battle_format="gen9randombattle",
        mode="auto",
        mission_goal="auto",
        rounds=2,
    )
    format_info = pokemon_api.pokemon_format_catalog.get("gen9randombattle")

    next_chain = pokemon_api._build_showdown_next_training_chain(
        payload=payload,
        format_info=format_info,
        training_health={
            "next_intervention": "review_blockers",
            "priority_actions": ["review_blockers"],
            "recommendation": "Review blockers.",
        },
    )

    assert next_chain["can_auto_continue"] is False
    assert next_chain["request"] is None
    assert next_chain["blocked_reason"] == "Review blockers."


def test_showdown_recovery_action_source_respects_custom_allowed_actions():
    recovery = {"status": "resume", "actions": ["connect", "flush_pending", "connect"]}

    source = pokemon_api._build_showdown_recovery_action_source(
        recovery,
        custom_allowed_actions=["start_search"],
    )

    assert source["status"] == "custom_override"
    assert source["actions"] == []


def test_showdown_recovery_action_source_applies_resume_actions():
    recovery = {"status": "resume", "actions": ["connect", "flush_pending", "connect"]}

    source = pokemon_api._build_showdown_recovery_action_source(
        recovery,
        custom_allowed_actions=None,
    )

    assert source["status"] == "applied"
    assert source["source"] == "previous_round_recovery"
    assert source["actions"] == ["connect", "flush_pending"]


def test_showdown_recovery_action_source_expands_stuck_recovery_actions():
    recovery = {
        "status": "resume",
        "actions": ["autopilot"],
        "previous_effectiveness": {
            "status": "stuck",
            "still_pending_actions": ["autopilot"],
        },
    }

    source = pokemon_api._build_showdown_recovery_action_source(
        recovery,
        custom_allowed_actions=None,
    )

    assert source["status"] == "expanded"
    assert source["base_actions"] == ["autopilot"]
    assert source["effectiveness_status"] == "stuck"
    assert source["actions"] == ["connect", "flush_pending", "start_search", "run_once", "autopilot", "analyze"]


@pytest.mark.asyncio
async def test_showdown_training_chain_expands_stuck_previous_chain_recovery(setup_db, client):
    previous = pokemon_api.pokemon_showdown_session_service.create_session(
        username="StuckCarryBot",
        team=None,
        battle_format="gen9randombattle",
    )
    pokemon_api.pokemon_showdown_session_service.store_training_chain_summary(
        previous.session_id,
        {
            "username": "StuckCarryBot",
            "battle_format": "gen9randombattle",
            "showdown_format": "gen9randombattle",
            "requested_rounds": 2,
            "completed_rounds": 2,
            "stop_reason": "round_limit",
            "mastery_score": 10,
            "progress": {"direction": "unchanged", "battle_delta": 0},
            "recovery": {
                "status": "resume",
                "actions": ["autopilot"],
                "action_counts": {"autopilot": 1},
                "task_count": 1,
                "rounds": [{"round": 2, "status": "resume", "actions": ["autopilot"], "task_count": 1}],
                "blocked_reasons": [],
                "recommendation": "Resume autopilot.",
            },
            "recovery_effectiveness": {
                "status": "stuck",
                "still_pending_actions": ["autopilot"],
                "applied_count": 1,
                "recovered_count": 0,
            },
            "rounds": [],
        },
    )

    response = await client.post(
        "/api/pokemon/showdown/training-chain",
        json={
            "username": "StuckCarryBot",
            "battle_format": "gen9randombattle",
            "mode": "auto",
            "mission_goal": "auto",
            "rounds": 1,
            "max_actions": 1,
            "send_commands": False,
            "stop_on_finished": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["rounds"][0]["recovery_action_source"]["status"] == "expanded"
    assert data["rounds"][0]["recovery_action_source"]["source"] == "previous_training_chain_recovery"
    assert data["rounds"][0]["recovery_action_source"]["base_actions"] == ["autopilot"]
    assert data["rounds"][0]["planned_actions"] == [
        "connect",
        "flush_pending",
        "start_search",
        "run_once",
        "autopilot",
        "analyze",
    ]
    assert data["training_health"]["status"] == "recovering"
    assert data["training_health"]["next_intervention"] == "resume_recovery"
    assert data["training_health"]["priority_actions"]
    assert data["training_chain_summary"]["rounds"][0]["recovery_action_source"]["status"] == "expanded"

    await client.delete(f"/api/pokemon/showdown/sessions/{previous.session_id}")
    for round_item in data["rounds"]:
        await client.delete(f"/api/pokemon/showdown/sessions/{round_item['session_id']}")


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
