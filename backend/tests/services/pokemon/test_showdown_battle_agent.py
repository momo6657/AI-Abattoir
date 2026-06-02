"""Tests for autonomous Pokemon Showdown battle choice planning."""

import json

from app.services.pokemon.showdown_battle_agent import PokemonShowdownBattleAgent


def test_plan_team_preview_uses_max_team_size_and_rqid():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 11,
        "teamPreview": True,
        "maxTeamSize": 4,
        "side": {
            "pokemon": [
                {"ident": "p1: Incineroar", "condition": "100/100"},
                {"ident": "p1: Flutter Mane", "condition": "100/100"},
                {"ident": "p1: Rillaboom", "condition": "100/100"},
                {"ident": "p1: Urshifu", "condition": "100/100"},
                {"ident": "p1: Amoonguss", "condition": "0 fnt"},
                {"ident": "p1: Tornadus", "condition": "100/100"},
            ]
        },
    }

    plan = agent.plan_from_raw_request(payload, "battle-gen9vgc-1")

    assert plan.decision_type == "team_preview"
    assert plan.command == "battle-gen9vgc-1|/choose team 1234|11"
    assert plan.choices == ["team 1234"]


def test_plan_force_switch_chooses_healthy_bench_and_passes_unforced_slot():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 12,
        "forceSwitch": [True, False],
        "side": {
            "pokemon": [
                {"ident": "p1: Incineroar", "condition": "20/100", "active": True},
                {"ident": "p1: Flutter Mane", "condition": "70/100", "active": True},
                {"ident": "p1: Rillaboom", "condition": "100/100"},
                {"ident": "p1: Urshifu", "condition": "0 fnt"},
            ]
        },
    }

    plan = agent.plan_from_raw_request(payload, "battle-gen9vgc-2")

    assert plan.decision_type == "force_switch"
    assert plan.command == "battle-gen9vgc-2|/choose switch 3, pass|12"
    assert plan.choices == ["switch 3", "pass"]


def test_plan_moves_skips_disabled_moves_targets_foe_and_can_tera():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 13,
        "active": [
            {
                "canTerastallize": True,
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "flareblitz", "target": "normal", "basePower": 120, "pp": 15},
                    {"id": "fakeout", "target": "normal", "basePower": 40, "disabled": True, "pp": 10},
                ],
            },
            {
                "moves": [
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                    {"id": "dazzlinggleam", "target": "allAdjacentFoes", "basePower": 80, "pp": 10},
                ],
            },
        ],
    }

    plan = agent.plan_from_raw_request(payload, "battle-gen9vgc-3", mode="aggressive")

    assert plan.decision_type == "move"
    assert plan.command == "battle-gen9vgc-3|/choose move 2 -1 terastallize, move 1 -1|13"
    assert plan.choices == ["move 2 -1 terastallize", "move 1 -1"]


def test_plan_wait_request_returns_no_command():
    agent = PokemonShowdownBattleAgent()

    plan = agent.plan_from_raw_request({"rqid": 14, "wait": True}, "battle-gen9vgc-4")

    assert plan.decision_type == "wait"
    assert plan.command is None
    assert not plan.needs_choice


def test_plan_from_payload_returns_events_request_and_plan():
    agent = PokemonShowdownBattleAgent()
    request = {"rqid": 15, "active": [{"moves": [{"id": "protect", "target": "self", "pp": 16}]}]}

    events, parsed_request, plan = agent.plan_from_payload(
        f">battle-gen9vgc-5\n|request|{json.dumps(request)}",
        mode="defensive",
    )

    assert events[0].event_type == "request"
    assert parsed_request is not None
    assert parsed_request.request_id == 15
    assert plan.command == "battle-gen9vgc-5|/choose move 1|15"
