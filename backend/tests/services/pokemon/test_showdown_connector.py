"""Tests for Pokemon Showdown protocol command helpers."""

import json

import pytest

from app.services.pokemon.showdown_connector import (
    PokemonShowdownConnector,
    ShowdownConnectionError,
)


def sample_team():
    return [
        {
            "species": "Incineroar",
            "ability": "Intimidate",
            "item": "Sitrus Berry",
            "moves": ["Flare Blitz", "Parting Shot", "Fake Out", "Snarl"],
            "nature": "Careful",
            "evs": {"hp": 252, "atk": 4, "def": 0, "spa": 0, "spd": 252, "spe": 0},
            "level": 50,
            "tera_type": "Grass",
        },
        {
            "species": "Flutter Mane",
            "name": "Moon",
            "ability": "Protosynthesis",
            "item": "Booster Energy",
            "moves": [{"name": "Moonblast"}, {"name": "Shadow Ball"}, {"name": "Protect"}],
            "nature": "Timid",
            "evs": {"hp": 4, "spa": 252, "spe": 252},
            "level": 50,
        },
    ]


def test_pack_team_uses_showdown_ids_and_vgc_level():
    connector = PokemonShowdownConnector()

    packed = connector.pack_team(sample_team())

    assert packed.startswith(
        "Incineroar||sitrusberry|intimidate|flareblitz,partingshot,fakeout,snarl|Careful|252,4,,,252|||"
    )
    assert "|50|,,,,,Grass]" in packed
    assert "Moon|Flutter Mane|boosterenergy|protosynthesis|moonblast,shadowball,protect|Timid|4,,,252,,252|||" in packed
    assert " " in packed  # Nickname/species fields preserve display names where Showdown expects names.


def test_build_ladder_search_messages_include_team_upload():
    connector = PokemonShowdownConnector()

    messages = connector.build_ladder_search_messages(sample_team(), "gen9vgc2024regg")

    assert messages[0].startswith("|/utm Incineroar||sitrusberry")
    assert messages[1] == "|/search gen9vgc2024regg"


def test_build_challenge_and_accept_messages():
    connector = PokemonShowdownConnector()

    challenge = connector.build_challenge_messages("Rival", "gen9vgc2024regg", None)
    accept = connector.build_accept_challenge_messages("Rival", "")

    assert challenge == ["|/utm null", "|/challenge Rival, gen9vgc2024regg"]
    assert accept == ["|/utm ", "|/accept Rival"]
    assert connector.build_reject_challenge_message("Rival") == "|/reject Rival"


def test_choose_builders_are_one_based_and_preserve_rqid():
    connector = PokemonShowdownConnector()

    assert connector.build_choose_team("battle-gen9vgc-1", [2, 1, 3, 4], 7) == "battle-gen9vgc-1|/choose team 2134|7"
    assert connector.build_choose_move("battle-gen9vgc-1", 1, -1, 8, "terastallize") == (
        "battle-gen9vgc-1|/choose move 1 -1 terastallize|8"
    )
    assert connector.build_choose_switch("battle-gen9vgc-1", 3, 9) == "battle-gen9vgc-1|/choose switch 3|9"
    assert connector.build_choose_multi("battle-gen9vgc-1", ["move 1 1", "move 2 -1"], 10) == (
        "battle-gen9vgc-1|/choose move 1 1, move 2 -1|10"
    )


def test_choose_builders_reject_zero_based_slots():
    connector = PokemonShowdownConnector()

    with pytest.raises(ValueError):
        connector.build_choose_move("battle-1", 0)
    with pytest.raises(ValueError):
        connector.build_choose_switch("battle-1", 0)
    with pytest.raises(ValueError):
        connector.build_choose_team("battle-1", [0, 1])


def test_parse_battle_request_from_room_payload():
    connector = PokemonShowdownConnector()
    request_payload = {
        "rqid": 3,
        "active": [{"moves": [{"id": "protect", "target": "self"}]}],
        "side": {"pokemon": [{"ident": "p1: Incineroar"}]},
    }
    events = connector.parse_message(f">battle-gen9vgc-42\n|request|{json.dumps(request_payload)}")

    request = connector.parse_battle_request(events)

    assert request is not None
    assert request.room_id == "battle-gen9vgc-42"
    assert request.request_id == 3
    assert request.needs_choice
    assert request.active[0]["moves"][0]["id"] == "protect"


def test_parse_battle_request_wait_state_does_not_need_choice():
    connector = PokemonShowdownConnector()
    events = connector.parse_message('>battle-gen9vgc-42\n|request|{"wait":true,"rqid":4}')

    request = connector.parse_battle_request(events)

    assert request is not None
    assert request.wait
    assert not request.needs_choice


def test_parse_battle_request_invalid_json_raises_connector_error():
    connector = PokemonShowdownConnector()
    events = connector.parse_message(">battle-gen9vgc-42\n|request|{bad")

    with pytest.raises(ShowdownConnectionError):
        connector.parse_battle_request(events)


def test_parse_search_and_challenge_updates():
    connector = PokemonShowdownConnector()
    events = connector.parse_message(
        '|updatesearch|{"searching":["gen9vgc2024regg"],"games":null}\n'
        '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg"},"challengeTo":null}'
    )

    assert connector.parse_search_update(events)["searching"] == ["gen9vgc2024regg"]
    assert connector.parse_challenge_update(events)["challengesFrom"]["rival"] == "gen9vgc2024regg"
