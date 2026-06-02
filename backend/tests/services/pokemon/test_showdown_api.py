"""API tests for Pokemon Showdown command and parse helpers."""

import json

import pytest


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
async def test_showdown_decision_requires_payload_or_request(client):
    response = await client.post("/api/pokemon/showdown/decision", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "payload or request is required."


@pytest.mark.asyncio
async def test_showdown_session_processes_payload_and_returns_commands(client):
    created = await client.post(
        "/api/pokemon/showdown/sessions",
        json={"username": "Bot", "team": None, "battle_format": "gen9vgc2024regg", "login_assertion": "ASSERT"},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]
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

    deleted = await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")
    assert deleted.status_code == 200


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
async def test_showdown_session_run_once_requires_connected_socket(client):
    created = await client.post("/api/pokemon/showdown/sessions", json={"username": "Bot", "team": None})
    session_id = created.json()["session_id"]

    response = await client.post(f"/api/pokemon/showdown/sessions/{session_id}/run-once", json={})

    assert response.status_code == 400
    assert "websocket is not connected" in response.json()["detail"]

    await client.delete(f"/api/pokemon/showdown/sessions/{session_id}")
