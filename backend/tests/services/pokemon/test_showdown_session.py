"""Tests for Pokemon Showdown autonomous session orchestration."""

import json

from app.services.pokemon.showdown_session import PokemonShowdownSessionService


def test_create_session_can_prepare_ladder_search_commands():
    service = PokemonShowdownSessionService()

    session = service.create_session(
        username="Bot",
        team=[{"species": "Incineroar", "ability": "Intimidate", "item": "Sitrus Berry", "moves": ["Fake Out"]}],
        battle_format="gen9vgc2024regg",
        auto_search=True,
    )

    assert session.status == "searching"
    assert session.command_log[0].startswith("|/utm Incineroar||sitrusberry|intimidate|fakeout")
    assert session.command_log[1] == "|/search gen9vgc2024regg"


def test_process_payload_logs_in_and_auto_responds_to_battle_request():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, login_assertion="ASSERT")
    request = {
        "rqid": 5,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }

    result = service.process_payload(
        session.session_id,
        f"|challstr|1|abc\n>battle-gen9vgc-1\n|init|battle\n|request|{json.dumps(request)}",
    )

    assert result["commands"] == ["|/trn Bot,0,ASSERT", "battle-gen9vgc-1|/choose move 2 -1|5"]
    assert result["session"]["status"] == "responded"
    assert result["session"]["rooms"] == ["battle-gen9vgc-1"]
    assert result["decision"]["decision_type"] == "move"


def test_process_payload_updates_search_challenges_and_result():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)

    result = service.process_payload(
        session.session_id,
        '|updatesearch|{"searching":["gen9vgc2024regg"]}\n'
        '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg"}}\n'
        ">battle-gen9vgc-2\n|win|Bot",
        auto_respond=False,
    )

    assert result["commands"] == []
    assert result["session"]["search"]["searching"] == ["gen9vgc2024regg"]
    assert result["session"]["challenges"]["challengesFrom"]["rival"] == "gen9vgc2024regg"
    assert result["session"]["status"] == "finished"
    assert result["session"]["result"] == {"type": "win", "winner": "Bot"}


def test_start_search_and_delete_session():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)

    commands = service.start_ladder_search(session.session_id)

    assert commands == ["|/utm null", "|/search gen9vgc2024regg"]
    assert service.delete_session(session.session_id)
    assert service.get_session(session.session_id) is None
