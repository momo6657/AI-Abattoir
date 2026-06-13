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
    assert plan.choice_details[0]["pokemon"] == "Incineroar"


def test_plan_team_preview_scores_leads_from_team_context_and_learning():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 22,
        "teamPreview": True,
        "maxTeamSize": 4,
        "side": {
            "pokemon": [
                {"ident": "p1: Flutter Mane", "condition": "100/100"},
                {"ident": "p1: Amoonguss", "condition": "100/100"},
                {"ident": "p1: Incineroar", "condition": "100/100"},
                {"ident": "p1: Tornadus", "condition": "100/100"},
                {"ident": "p1: Urshifu", "condition": "100/100"},
                {"ident": "p1: Rillaboom", "condition": "100/100"},
            ]
        },
    }
    team_context = [
        {"species": "Flutter Mane", "moves": ["Moonblast", "Dazzling Gleam"]},
        {"species": "Amoonguss", "moves": ["Spore", "Rage Powder", "Protect"]},
        {"species": "Incineroar", "ability": "Intimidate", "item": "Sitrus Berry", "moves": ["Fake Out", "Parting Shot"]},
        {"species": "Tornadus", "moves": ["Tailwind", "Taunt"]},
        {"species": "Urshifu", "moves": ["Surging Strikes", "Close Combat"]},
        {"species": "Rillaboom", "moves": ["Fake Out", "Wood Hammer"]},
    ]

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-12",
        team_context=team_context,
        learning_profile={
            "battles": 3,
            "win_rate": 0.0,
            "average_reward": 10.0,
            "faints_for": 1,
            "faints_against": 5,
        },
    )

    assert plan.command == "battle-gen9vgc-12|/choose team 3246|22"
    assert "Lead order was scored" in plan.reason
    assert [detail["pokemon"] for detail in plan.choice_details] == ["Incineroar", "Amoonguss", "Tornadus", "Rillaboom"]
    assert plan.choice_details[0]["strategy_used"]
    assert any(detail["learning_used"] for detail in plan.choice_details)


def test_plan_team_preview_uses_opponent_preview_context():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 25,
        "teamPreview": True,
        "maxTeamSize": 1,
        "side": {
            "pokemon": [
                {"ident": "p1: Tornadus", "condition": "100/100"},
                {"ident": "p1: Flutter Mane", "condition": "100/100"},
            ]
        },
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-14",
        team_context=[
            {"species": "Tornadus", "moves": ["Tailwind", "Taunt"]},
            {"species": "Flutter Mane", "moves": ["Moonblast"]},
        ],
        battlefield_context={
            "opponent_preview": [
                {"species": "Miraidon", "details": "Miraidon, L50"},
                {"species": "Urshifu", "details": "Urshifu, L50"},
            ]
        },
    )

    assert plan.command == "battle-gen9vgc-14|/choose team 1|25"
    assert plan.choice_details[0]["pokemon"] == "Tornadus"
    assert plan.choice_details[0]["opponent_preview_used"]
    assert "opponent preview" in plan.choice_details[0]["reason"]


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
    assert plan.choice_details[0]["pokemon"] == "Rillaboom"
    assert plan.choice_details[1]["reason"] == "slot was not forced to switch"


def test_plan_force_switch_scores_bench_roles_and_opponent_preview():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 27,
        "forceSwitch": [True],
        "side": {
            "pokemon": [
                {"ident": "p1: Flutter Mane", "condition": "0 fnt", "active": True},
                {"ident": "p1: Tornadus", "condition": "70/100", "active": True},
                {"ident": "p1: Incineroar", "condition": "60/100"},
                {"ident": "p1: Amoonguss", "condition": "100/100"},
            ]
        },
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-16",
        team_context=[
            {"species": "Flutter Mane", "moves": ["Moonblast"]},
            {"species": "Tornadus", "moves": ["Tailwind"]},
            {"species": "Incineroar", "ability": "Intimidate", "moves": ["Fake Out", "Parting Shot"]},
            {"species": "Amoonguss", "moves": ["Spore", "Rage Powder", "Protect"]},
        ],
        battlefield_context={
            "opponent_preview": [
                {"species": "Koraidon", "details": "Koraidon, L50"},
                {"species": "Urshifu", "details": "Urshifu, L50"},
            ]
        },
    )

    assert plan.command == "battle-gen9vgc-16|/choose switch 3|27"
    assert plan.choice_details[0]["pokemon"] == "Incineroar"
    assert plan.choice_details[0]["strategy_used"]
    assert plan.choice_details[0]["opponent_preview_used"]


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
    assert plan.choice_details[0]["move"] == "flareblitz"
    assert plan.choice_details[0]["modifier"] == "terastallize"
    assert plan.choice_details[0]["legal_candidates"][0]["move"] == "flareblitz"


def test_plan_moves_fallback_switches_when_no_legal_moves_and_not_trapped():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 29,
        "active": [
            {
                "trapped": False,
                "moves": [
                    {"id": "moonblast", "target": "normal", "pp": 0},
                    {"id": "protect", "target": "self", "disabled": True, "pp": 16},
                ],
            }
        ],
        "side": {
            "pokemon": [
                {"ident": "p1: Flutter Mane", "condition": "40/100", "active": True},
                {"ident": "p1: Incineroar", "condition": "100/100"},
            ]
        },
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-17",
        team_context=[
            {"species": "Flutter Mane", "moves": ["Moonblast"]},
            {"species": "Incineroar", "ability": "Intimidate", "moves": ["Fake Out", "Parting Shot"]},
        ],
    )

    assert plan.command == "battle-gen9vgc-17|/choose switch 2|29"
    assert plan.choice_details[0]["fallback_switch"]
    assert plan.choice_details[0]["pokemon"] == "Incineroar"


def test_plan_moves_defaults_when_no_legal_moves_and_trapped():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 30,
        "active": [
            {
                "trapped": True,
                "moves": [
                    {"id": "moonblast", "target": "normal", "pp": 0},
                ],
            }
        ],
        "side": {
            "pokemon": [
                {"ident": "p1: Flutter Mane", "condition": "40/100", "active": True},
                {"ident": "p1: Incineroar", "condition": "100/100"},
            ]
        },
    }

    plan = agent.plan_from_raw_request(payload, "battle-gen9vgc-18")

    assert plan.command == "battle-gen9vgc-18|/choose default|30"
    assert plan.choice_details[0]["choice"] == "default"
    assert "no legal moves" in plan.choice_details[0]["reason"]


def test_plan_moves_targets_weakened_opponent_from_battlefield_context():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 24,
        "active": [
            {
                "moves": [
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ],
            }
        ],
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-13",
        active_pokemon=2,
        battlefield_context={
            "opponents": [
                {"position": "a", "active": True, "fainted": False, "hp_fraction": 0.8, "pokemon": "Urshifu"},
                {"position": "b", "active": True, "fainted": False, "hp_fraction": 0.25, "pokemon": "Flutter Mane"},
            ]
        },
    )

    assert plan.command == "battle-gen9vgc-13|/choose move 1 -2|24"
    assert plan.choice_details[0]["target"] == -2


def test_plan_moves_uses_matchup_preview_to_disrupt_speed_control():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 31,
        "active": [
            {
                "moves": [
                    {"id": "flareblitz", "target": "normal", "basePower": 120, "pp": 15},
                    {"id": "fakeout", "target": "normal", "basePower": 40, "pp": 10},
                ],
            }
        ],
        "side": {
            "pokemon": [
                {"ident": "p1: Incineroar", "condition": "100/100", "active": True},
            ]
        },
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-19",
        active_pokemon=2,
        battlefield_context={
            "opponent_preview": [
                {"species": "Tornadus", "details": "Tornadus, L50"},
                {"species": "Amoonguss", "details": "Amoonguss, L50"},
            ]
        },
    )

    assert plan.command == "battle-gen9vgc-19|/choose move 2 -1|31"
    assert plan.choice_details[0]["move"] == "fakeout"
    assert plan.choice_details[0]["matchup_used"]
    assert "matchup context prioritizes disrupting preview threats" in plan.choice_details[0]["reason"]
    assert plan.choice_details[0]["legal_candidates"][0]["matchup_used"]


def test_plan_moves_uses_active_matchup_to_protect_against_spread_damage():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 32,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ],
            }
        ],
        "side": {
            "pokemon": [
                {"ident": "p1: Flutter Mane", "condition": "100/100", "active": True},
            ]
        },
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-20",
        active_pokemon=2,
        battlefield_context={
            "opponents": [
                {"position": "a", "active": True, "fainted": False, "hp_fraction": 1.0, "pokemon": "Gholdengo"},
                {"position": "b", "active": True, "fainted": False, "hp_fraction": 1.0, "pokemon": "Tornadus"},
            ]
        },
    )

    assert plan.command == "battle-gen9vgc-20|/choose move 1|32"
    assert plan.choice_details[0]["move"] == "protect"
    assert plan.choice_details[0]["matchup_used"]
    assert "matchup context favors protecting into spread damage" in plan.choice_details[0]["reason"]


def test_plan_moves_prioritizes_tactical_utility_and_avoids_self_ko():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 16,
        "active": [
            {
                "moves": [
                    {"id": "explosion", "target": "allAdjacent", "basePower": 250, "pp": 5},
                    {"id": "fakeout", "target": "normal", "basePower": 40, "pp": 10},
                    {"id": "tackle", "target": "normal", "basePower": 40, "pp": 35},
                ],
            },
            {
                "moves": [
                    {"id": "tailwind", "target": "allySide", "pp": 15},
                    {"id": "airslash", "target": "normal", "basePower": 75, "pp": 15},
                ],
            },
        ],
    }

    plan = agent.plan_from_raw_request(payload, "battle-gen9vgc-6", mode="balanced")

    assert plan.command == "battle-gen9vgc-6|/choose move 2 -1, move 1|16"
    assert plan.choice_details[0]["move"] == "fakeout"
    assert plan.choice_details[1]["move"] == "tailwind"
    assert plan.choice_details[0]["legal_candidates"][-1]["move"] == "explosion"


def test_plan_moves_uses_knowledge_context_as_lightweight_bonus():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 17,
        "active": [
            {
                "moves": [
                    {"id": "flareblitz", "target": "normal", "basePower": 80, "pp": 15},
                    {"id": "knockoff", "target": "normal", "basePower": 75, "pp": 20},
                ],
            }
        ],
        "side": {
            "pokemon": [
                {"ident": "p1: Incineroar, L50, M", "condition": "100/100", "active": True},
            ]
        },
    }
    knowledge_context = {
        "members": [
            {
                "species": "Incineroar",
                "results": [{"title": "Incineroar VGC usage: Knock Off, Parting Shot, Fake Out"}],
            }
        ]
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-7",
        knowledge_context=knowledge_context,
    )

    assert plan.command == "battle-gen9vgc-7|/choose move 2 -1|17"
    assert plan.choice_details[0]["pokemon"] == "Incineroar"
    assert plan.choice_details[0]["move"] == "knockoff"
    assert plan.choice_details[0]["knowledge_used"]
    assert "knowledge context mentions this move" in plan.choice_details[0]["reason"]
    assert plan.choice_details[0]["legal_candidates"][0]["knowledge_used"]


def test_plan_moves_uses_weak_learning_profile_for_safer_play():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 20,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ],
            }
        ],
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9vgc-8",
        learning_profile={
            "battles": 3,
            "win_rate": 0.0,
            "average_reward": 10.0,
            "faints_for": 1,
            "faints_against": 5,
        },
    )

    assert plan.command == "battle-gen9vgc-8|/choose move 1|20"
    assert "Learning profile nudged" in plan.reason
    assert plan.choice_details[0]["move"] == "protect"
    assert plan.choice_details[0]["learning_used"]
    assert "learning profile favors safer play" in plan.choice_details[0]["reason"]
    assert plan.choice_details[0]["legal_candidates"][0]["learning_used"]


def test_plan_moves_omits_target_for_singles_format():
    agent = PokemonShowdownBattleAgent()
    payload = {
        "rqid": 19,
        "active": [
            {
                "moves": [
                    {"id": "shadowball", "target": "normal", "basePower": 80, "pp": 15},
                    {"id": "protect", "target": "self", "pp": 16},
                ],
            }
        ],
    }

    plan = agent.plan_from_raw_request(
        payload,
        "battle-gen9ou-1",
        active_pokemon=1,
    )

    assert plan.command == "battle-gen9ou-1|/choose move 1|19"
    assert plan.choices == ["move 1"]
    assert plan.choice_details[0]["target"] is None


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
    assert plan.choice_details[0]["reason"] == "protective move scored for defensive mode"
