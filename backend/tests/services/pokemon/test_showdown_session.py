"""Tests for Pokemon Showdown autonomous session orchestration."""

import json

import pytest

from app.services.pokemon.showdown_connector import PokemonShowdownConnector
from app.services.pokemon.showdown_session import PokemonShowdownSessionService


class FakeShowdownConnector(PokemonShowdownConnector):
    def __init__(self, incoming: list[str] | None = None):
        super().__init__()
        self.incoming = incoming or []
        self.sent: list[str] = []
        self.connected = False
        self.closed = False
        self.assertion_requests: list[dict[str, str | None]] = []

    async def connect(self) -> None:
        self.connected = True
        self.websocket = object()

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def receive(self) -> str:
        if not self.incoming:
            raise RuntimeError("No fake Showdown payload available.")
        return self.incoming.pop(0)

    async def close(self) -> None:
        self.closed = True
        self.websocket = None

    async def request_assertion(self, username: str, challstr: str, password: str | None = None) -> str:
        self.assertion_requests.append({"username": username, "challstr": challstr, "password": password})
        return "ASSERT-FROM-PS"


def test_create_session_can_prepare_ladder_search_commands():
    service = PokemonShowdownSessionService()

    session = service.create_session(
        username="Bot",
        team=[{"species": "Incineroar", "ability": "Intimidate", "item": "Sitrus Berry", "moves": ["Fake Out"]}],
        battle_format="vgc2024",
        auto_search=True,
    )

    assert session.status == "searching"
    assert session.battle_format == "vgc2024"
    assert session.showdown_format == "gen9vgc2024regg"
    assert session.team_size == 4
    assert session.command_log[0].startswith("|/utm Incineroar||sitrusberry|intimidate|fakeout")
    assert session.command_log[1] == "|/search gen9vgc2024regg"


def test_create_session_exposes_provided_team_preview():
    service = PokemonShowdownSessionService()

    session = service.create_session(
        username="Bot",
        team=[
            {
                "species": "Incineroar",
                "ability": "Intimidate",
                "item": "Sitrus Berry",
                "moves": [{"name": "Fake Out"}, "Parting Shot"],
                "tera_type": "Grass",
            }
        ],
        battle_format="vgc2024",
    )
    preview = session.to_dict()["team_preview"]

    assert preview == [
        {
            "slot": 1,
            "species": "Incineroar",
            "name": None,
            "item": "Sitrus Berry",
            "ability": "Intimidate",
            "tera_type": "Grass",
            "moves": ["Fake Out", "Parting Shot"],
        }
    ]


def test_create_session_records_auto_research_flag():
    service = PokemonShowdownSessionService()

    session = service.create_session(username="Bot", team=None, auto_research_team=True)

    assert session.auto_research_team
    assert session.to_dict()["auto_research_team"]


def test_create_session_applies_learning_profile_to_auto_team():
    service = PokemonShowdownSessionService()

    session = service.create_session(
        username="Bot",
        team=None,
        battle_format="vgc2024",
        learning_profile={
            "battles": 2,
            "win_rate": 0.0,
            "average_reward": 20.0,
            "faints_for": 1,
            "faints_against": 5,
        },
    )
    snapshot = session.to_dict()

    assert snapshot["team_source"] == "learned_template"
    assert snapshot["team_adjustments"]
    assert any(adjustment["title"] == "Added Protect safety" for adjustment in snapshot["team_adjustments"])
    assert "Applied learned safety adjustments" in snapshot["team_reason"]


def test_create_random_battle_session_uses_no_team_showdown_format():
    service = PokemonShowdownSessionService()

    session = service.create_session(username="Bot", team=None, battle_format="random", auto_search=True)

    assert session.battle_format == "gen9randombattle"
    assert session.showdown_format == "gen9randombattle"
    assert not session.requires_team
    assert session.team_source == "not_required"
    assert session.command_log == ["|/utm null", "|/search gen9randombattle"]


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


def test_process_payload_deduplicates_repeated_showdown_request_id():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)
    request = {
        "rqid": 51,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }
    payload = f">battle-gen9vgc-51\n|request|{json.dumps(request)}"

    first = service.process_payload(session.session_id, payload)
    repeated = service.process_payload(session.session_id, payload)

    assert first["commands"] == ["battle-gen9vgc-51|/choose move 2 -1|51"]
    assert repeated["commands"] == []
    assert repeated["decision"]["decision_type"] == "duplicate_request"
    assert repeated["session"]["handled_request_count"] == 1
    assert repeated["session"]["duplicate_request_count"] == 1
    assert repeated["session"]["command_log"] == ["battle-gen9vgc-51|/choose move 2 -1|51"]
    assert repeated["session"]["decision_count"] == 1


def test_process_payload_scores_team_preview_from_session_team():
    service = PokemonShowdownSessionService()
    session = service.create_session(
        username="Bot",
        battle_format="vgc2024",
        team=[
            {"species": "Flutter Mane", "moves": ["Moonblast", "Dazzling Gleam"]},
            {"species": "Amoonguss", "moves": ["Spore", "Rage Powder", "Protect"]},
            {"species": "Incineroar", "ability": "Intimidate", "item": "Sitrus Berry", "moves": ["Fake Out", "Parting Shot"]},
            {"species": "Tornadus", "moves": ["Tailwind", "Taunt"]},
            {"species": "Urshifu", "moves": ["Surging Strikes", "Close Combat"]},
            {"species": "Rillaboom", "moves": ["Fake Out", "Wood Hammer"]},
        ],
        learning_profile={
            "battles": 3,
            "win_rate": 0.0,
            "average_reward": 10.0,
            "faints_for": 1,
            "faints_against": 5,
        },
    )
    request = {
        "rqid": 7,
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

    result = service.process_payload(
        session.session_id,
        f">battle-gen9vgc-12\n|request|{json.dumps(request)}",
    )

    assert result["commands"] == ["battle-gen9vgc-12|/choose team 3246|7"]
    assert result["decision"]["decision_type"] == "team_preview"
    assert result["decision"]["choice_details"][0]["pokemon"] == "Incineroar"
    assert any(detail["learning_used"] for detail in result["decision"]["choice_details"])


def test_process_payload_syncs_poke_preview_and_uses_it_for_leads():
    service = PokemonShowdownSessionService()
    session = service.create_session(
        username="Bot",
        battle_format="vgc2024",
        team=[
            {"species": "Tornadus", "moves": ["Tailwind", "Taunt"]},
            {"species": "Flutter Mane", "moves": ["Moonblast"]},
        ],
    )
    request = {
        "rqid": 26,
        "teamPreview": True,
        "maxTeamSize": 1,
        "side": {
            "pokemon": [
                {"ident": "p1: Tornadus", "condition": "100/100"},
                {"ident": "p1: Flutter Mane", "condition": "100/100"},
            ]
        },
    }

    result = service.process_payload(
        session.session_id,
        ">battle-gen9vgc-15\n"
        "|player|p1|Bot\n"
        "|player|p2|Rival\n"
        "|poke|p2|Miraidon, L50|\n"
        "|poke|p2|Urshifu, L50|\n"
        f"|request|{json.dumps(request)}",
        team_size=1,
    )
    room = result["session"]["room_details"]["battle-gen9vgc-15"]

    assert result["commands"] == ["battle-gen9vgc-15|/choose team 1|26"]
    assert room["preview"]["p2"][0]["species"] == "Miraidon"
    assert room["preview"]["p2"][1]["details"] == "Urshifu, L50"
    assert result["decision"]["choice_details"][0]["pokemon"] == "Tornadus"
    assert result["decision"]["choice_details"][0]["opponent_preview_used"]


def test_process_payload_uses_room_preview_for_forced_switch():
    service = PokemonShowdownSessionService()
    session = service.create_session(
        username="Bot",
        battle_format="vgc2024",
        team=[
            {"species": "Flutter Mane", "moves": ["Moonblast"]},
            {"species": "Tornadus", "moves": ["Tailwind"]},
            {"species": "Incineroar", "ability": "Intimidate", "moves": ["Fake Out", "Parting Shot"]},
            {"species": "Amoonguss", "moves": ["Spore", "Rage Powder", "Protect"]},
        ],
    )
    request = {
        "rqid": 28,
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

    result = service.process_payload(
        session.session_id,
        ">battle-gen9vgc-16\n"
        "|player|p1|Bot\n"
        "|player|p2|Rival\n"
        "|poke|p2|Koraidon, L50|\n"
        "|poke|p2|Urshifu, L50|\n"
        f"|request|{json.dumps(request)}",
    )

    assert result["commands"] == ["battle-gen9vgc-16|/choose switch 3|28"]
    assert result["decision"]["choice_details"][0]["pokemon"] == "Incineroar"
    assert result["decision"]["choice_details"][0]["opponent_preview_used"]


def test_process_payload_targets_weakened_opponent_from_room_state():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)
    service.process_payload(
        session.session_id,
        ">battle-gen9vgc-13\n"
        "|player|p1|Bot\n"
        "|player|p2|Rival\n"
        "|switch|p2a: Urshifu|Urshifu, L50|80/100\n"
        "|switch|p2b: Flutter Mane|Flutter Mane, L50|25/100",
        auto_respond=False,
    )
    request = {
        "rqid": 8,
        "active": [
            {
                "moves": [
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }

    result = service.process_payload(
        session.session_id,
        f">battle-gen9vgc-13\n|request|{json.dumps(request)}",
    )
    room = result["session"]["room_details"]["battle-gen9vgc-13"]

    assert result["commands"] == ["battle-gen9vgc-13|/choose move 1 -2|8"]
    assert result["decision"]["choice_details"][0]["target"] == -2
    assert room["battlefield"]["sides"]["p2"]["active"]["b"]["hp_fraction"] == 0.25


def test_process_payload_uses_learning_profile_for_move_choice():
    service = PokemonShowdownSessionService()
    session = service.create_session(
        username="Bot",
        team=None,
        learning_profile={
            "battles": 3,
            "win_rate": 0.0,
            "average_reward": 10.0,
            "faints_for": 1,
            "faints_against": 5,
        },
    )
    request = {
        "rqid": 6,
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
        f">battle-gen9vgc-11\n|request|{json.dumps(request)}",
    )

    assert result["commands"] == ["battle-gen9vgc-11|/choose move 1|6"]
    assert result["decision"]["choice_details"][0]["move"] == "protect"
    assert result["decision"]["choice_details"][0]["learning_used"]
    assert result["session"]["decisions"][0]["choice_details"][0]["learning_used"]


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
    assert result["session"]["analysis"]["status"] == "win"
    assert result["session"]["analysis"]["reward"] == 100.0


def test_process_payload_updates_showdown_analysis_signals():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)

    result = service.process_payload(
        session.session_id,
        ">battle-gen9vgc-3\n"
        "|player|p1|Bot\n"
        "|player|p2|Rival\n"
        "|turn|3\n"
        "|move|p1a: Flutter Mane|Moonblast|p2a: Urshifu\n"
        "|-damage|p2a: Urshifu|0 fnt\n"
        "|faint|p2a: Urshifu\n"
        "|win|Bot",
        auto_respond=False,
    )

    analysis = result["session"]["analysis"]
    assert analysis["agent_side"] == "p1"
    assert analysis["turns"] == 3
    assert analysis["moves"] == 1
    assert analysis["damage_events"] == 1
    assert analysis["faints_for"] == 1
    assert analysis["reward"] == 120.0
    assert result["learning_profile"]["battles"] == 1
    assert result["learning_profile"]["wins"] == 1
    assert result["learning_profile"]["average_reward"] == 120.0
    assert result["session"]["learning_profile"]["battles"] == 1
    assert session.to_dict()["learning_profile"]["wins"] == 1

    refreshed = service.analyze_session(session.session_id)
    assert refreshed == analysis
    profile = service.learning_profile("Bot", "vgc2024")
    assert profile["battles"] == 1
    assert profile["recommendation"]["mode"] == "balanced"


def test_process_payload_syncs_showdown_room_metadata():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)

    result = service.process_payload(
        session.session_id,
        ">battle-gen9vgc-42\n"
        "|init|battle\n"
        "|title|Bot vs. Rival\n"
        "|gametype|doubles\n"
        "|gen|9\n"
        "|tier|VGC 2024 Reg G\n"
        "|rated|Rated battle\n"
        "|rule|Species Clause: Limit one of each Pokemon\n"
        "|player|p1|Bot|101|1500\n"
        "|player|p2|Rival|202|1525\n"
        '|request|{"rqid":12,"wait":true}\n'
        "|win|Rival",
        auto_respond=False,
    )
    room = result["session"]["room_details"]["battle-gen9vgc-42"]

    assert result["session"]["rooms"] == ["battle-gen9vgc-42"]
    assert room["title"] == "Bot vs. Rival"
    assert room["game_type"] == "doubles"
    assert room["generation"] == 9
    assert room["tier"] == "VGC 2024 Reg G"
    assert room["rated"]
    assert room["rules"] == ["Species Clause: Limit one of each Pokemon"]
    assert room["agent_side"] == "p1"
    assert room["opponent_username"] == "Rival"
    assert room["players"]["p2"]["rating"] == "1525"
    assert room["request_id"] == 12
    assert room["waiting"]
    assert room["status"] == "finished"
    assert room["result"] == {"type": "win", "winner": "Rival"}


def test_start_search_and_delete_session():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)

    commands = service.start_ladder_search(session.session_id)

    assert session.team_source == "template"
    assert len(session.team_species) == 4
    assert commands[0].startswith("|/utm ")
    assert commands[0] != "|/utm null"
    assert commands[1] == "|/search gen9vgc2024regg"
    assert session.to_dict()["pending_command_count"] == 2
    assert session.to_dict()["last_command"] == "|/search gen9vgc2024regg"
    assert service.delete_session(session.session_id)
    assert service.get_session(session.session_id) is None


def test_cancel_ladder_search_records_cancel_command():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, auto_search=True)

    commands = service.cancel_ladder_search(session.session_id)
    snapshot = session.to_dict()

    assert commands == ["|/cancelsearch"]
    assert session.status == "ready"
    assert snapshot["pending_command_count"] == 3
    assert snapshot["last_command"] == "|/cancelsearch"


def test_accept_and_reject_challenge_queue_session_commands():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)
    service.process_payload(
        session.session_id,
        '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg"}}',
        auto_respond=False,
    )

    accepted = service.accept_challenge(session.session_id)
    rejected = service.reject_challenge(session.session_id, "rival")
    snapshot = session.to_dict()

    assert accepted[0].startswith("|/utm ")
    assert accepted[1] == "|/accept rival"
    assert rejected == ["|/reject rival"]
    assert snapshot["challenge_count"] == 1
    assert snapshot["challenge_usernames"] == ["rival"]
    assert snapshot["pending_command_count"] == 3
    assert snapshot["last_command"] == "|/reject rival"


def test_auto_accept_challenge_accepts_matching_format_only_once():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, auto_accept_challenges=True)

    result = service.process_payload(
        session.session_id,
        '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg"}}',
        auto_respond=False,
    )
    repeated = service.process_payload(
        session.session_id,
        '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg"}}',
        auto_respond=False,
    )

    assert result["commands"][0].startswith("|/utm ")
    assert result["commands"][1] == "|/accept rival"
    assert result["session"]["status"] == "challenge_accepted"
    assert result["session"]["auto_accept_challenges"]
    assert result["session"]["accepted_challenges"] == ["rival"]
    assert repeated["commands"] == []


def test_auto_accept_challenge_ignores_mismatched_format():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, battle_format="gen9ou", auto_accept_challenges=True)

    result = service.process_payload(
        session.session_id,
        '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg"}}',
        auto_respond=False,
    )

    assert result["commands"] == []
    assert result["session"]["challenge_count"] == 1
    assert result["session"]["accepted_challenges"] == []


def test_accept_challenge_requires_known_or_explicit_challenger():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)

    with pytest.raises(ValueError):
        service.accept_challenge(session.session_id)

    commands = service.accept_challenge(session.session_id, "manual-rival")

    assert commands[1] == "|/accept manual-rival"


def test_create_singles_session_auto_generates_showdown_team():
    service = PokemonShowdownSessionService()

    session = service.create_session(username="Bot", team=None, battle_format="gen9ou", auto_search=True)

    assert session.battle_format == "gen9ou"
    assert session.showdown_format == "gen9ou"
    assert session.team_source == "showdown_factory"
    assert session.team_species == ["Great Tusk", "Kingambit", "Gholdengo", "Dragapult", "Iron Valiant", "Ting-Lu"]
    preview = session.to_dict()["team_preview"]
    assert len(preview) == 6
    assert preview[0]["species"] == "Great Tusk"
    assert preview[0]["item"] == "Booster Energy"
    assert preview[0]["ability"] == "Protosynthesis"
    assert preview[0]["tera_type"] == "Ground"
    assert preview[0]["moves"] == ["Headlong Rush", "Close Combat", "Rapid Spin", "Knock Off"]
    assert session.command_log[0].startswith("|/utm Great Tusk||boosterenergy|protosynthesis|")
    assert "|50|" not in session.command_log[0]
    assert session.command_log[1] == "|/search gen9ou"


def test_attach_knowledge_context_updates_session_snapshot():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)

    updated = service.attach_knowledge_context(
        session.session_id,
        {"member_count": 1, "sources": ["https://example.com/Incineroar"]},
    )
    snapshot = updated.to_dict()

    assert snapshot["has_knowledge_context"]
    assert snapshot["knowledge_context"]["member_count"] == 1
    assert snapshot["knowledge_context"]["sources"] == ["https://example.com/Incineroar"]


def test_process_payload_passes_attached_knowledge_context_to_decision():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None)
    service.attach_knowledge_context(
        session.session_id,
        {
            "members": [
                {
                    "species": "Incineroar",
                    "results": [{"title": "Incineroar teams commonly use Knock Off"}],
                }
            ]
        },
    )
    request = {
        "rqid": 32,
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

    result = service.process_payload(
        session.session_id,
        f">battle-gen9vgc-9\n|request|{json.dumps(request)}",
    )

    assert result["commands"] == ["battle-gen9vgc-9|/choose move 2 -1|32"]
    assert result["decision"]["choice_details"][0]["knowledge_used"]
    assert result["session"]["has_knowledge_context"]


def test_process_payload_uses_singles_target_policy_for_ou_session():
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, battle_format="gen9ou")
    request = {
        "rqid": 33,
        "active": [
            {
                "moves": [
                    {"id": "shadowball", "target": "normal", "basePower": 80, "pp": 15},
                    {"id": "protect", "target": "self", "pp": 16},
                ]
            }
        ],
    }

    result = service.process_payload(
        session.session_id,
        f">battle-gen9ou-10\n|request|{json.dumps(request)}",
    )

    assert session.active_pokemon == 1
    assert result["commands"] == ["battle-gen9ou-10|/choose move 1|33"]
    assert result["decision"]["choice_details"][0]["target"] is None


@pytest.mark.asyncio
async def test_connect_flushes_pending_commands_to_connector():
    connector = FakeShowdownConnector()
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, auto_search=True, connector=connector)

    result = await service.connect_session(session.session_id)

    assert connector.connected
    assert result["sent"][0].startswith("|/utm ")
    assert result["sent"][0] != "|/utm null"
    assert result["sent"][1] == "|/search gen9vgc2024regg"
    assert connector.sent == result["sent"]
    assert result["session"]["sent_log"] == result["sent"]
    assert result["session"]["pending_command_count"] == 0
    assert result["session"]["sent_count"] == 2


@pytest.mark.asyncio
async def test_flush_pending_commands_sends_accepted_challenge():
    connector = FakeShowdownConnector()
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, connector=connector)
    await service.connect_session(session.session_id, send_pending=False)
    service.process_payload(
        session.session_id,
        '|updatechallenges|{"challengesFrom":{"rival":"gen9vgc2024regg"}}',
        auto_respond=False,
    )
    service.accept_challenge(session.session_id)

    sent = await service.flush_pending_commands(session.session_id)

    assert sent[0].startswith("|/utm ")
    assert sent[1] == "|/accept rival"
    assert connector.sent == sent
    assert session.to_dict()["pending_command_count"] == 0


@pytest.mark.asyncio
async def test_run_once_receives_payload_auto_responds_and_sends_command():
    request = {
        "rqid": 31,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }
    connector = FakeShowdownConnector([f">battle-gen9vgc-7\n|request|{json.dumps(request)}"])
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, connector=connector)

    result = await service.run_once(session.session_id)

    assert result["commands"] == ["battle-gen9vgc-7|/choose move 2 -1|31"]
    assert result["sent"] == ["battle-gen9vgc-7|/choose move 2 -1|31"]
    assert connector.sent == ["battle-gen9vgc-7|/choose move 2 -1|31"]
    assert result["session"]["status"] == "responded"


@pytest.mark.asyncio
async def test_run_once_auto_requests_assertion_from_challstr():
    connector = FakeShowdownConnector(["|challstr|42|abcdef"])
    service = PokemonShowdownSessionService()
    session = service.create_session(
        username="Bot",
        team=None,
        login_password="SECRET",
        connector=connector,
    )

    result = await service.run_once(session.session_id)

    assert connector.assertion_requests == [{"username": "Bot", "challstr": "42|abcdef", "password": "SECRET"}]
    assert result["commands"] == ["|/trn Bot,0,ASSERT-FROM-PS"]
    assert result["sent"] == ["|/trn Bot,0,ASSERT-FROM-PS"]
    assert result["session"]["status"] == "authenticated"
    assert result["session"]["has_login_assertion"]
    assert result["session"]["has_login_password"]
    assert "SECRET" not in json.dumps(result["session"])


@pytest.mark.asyncio
async def test_run_once_can_disable_auto_login():
    connector = FakeShowdownConnector(["|challstr|42|abcdef"])
    service = PokemonShowdownSessionService()
    session = service.create_session(
        username="Bot",
        team=None,
        auto_login=False,
        connector=connector,
    )

    result = await service.run_once(session.session_id)

    assert connector.assertion_requests == []
    assert result["commands"] == []
    assert result["sent"] == []
    assert not result["session"]["has_login_assertion"]


@pytest.mark.asyncio
async def test_run_until_stops_on_finished_and_close_marks_closed():
    connector = FakeShowdownConnector([
        ">battle-gen9vgc-8\n|init|battle",
        ">battle-gen9vgc-8\n|win|Bot",
    ])
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, connector=connector)

    result = await service.run_until(session.session_id, max_messages=10)
    closed = await service.close_session(session.session_id)

    assert len(result["steps"]) == 2
    assert result["session"]["status"] == "finished"
    assert result["session"]["result"] == {"type": "win", "winner": "Bot"}
    assert connector.closed
    assert closed["status"] == "finished"


@pytest.mark.asyncio
async def test_autopilot_connects_searches_responds_and_stops_on_result():
    request = {
        "rqid": 41,
        "active": [
            {
                "moves": [
                    {"id": "protect", "target": "self", "pp": 16},
                    {"id": "moonblast", "target": "normal", "basePower": 95, "pp": 15},
                ]
            }
        ],
    }
    connector = FakeShowdownConnector([
        f">battle-gen9vgc-11\n|request|{json.dumps(request)}",
        ">battle-gen9vgc-11\n|win|Bot",
    ])
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, connector=connector, auto_login=False)

    result = await service.autopilot(session.session_id, max_messages=5, auto_search=True)

    assert result["actions"] == ["connected", "search_queued"]
    assert result["sent"][0].startswith("|/utm ")
    assert result["sent"][1] == "|/search gen9vgc2024regg"
    assert connector.sent[2] == "battle-gen9vgc-11|/choose move 2 -1|41"
    assert len(result["steps"]) == 2
    assert result["session"]["status"] == "finished"
    assert result["session"]["result"] == {"type": "win", "winner": "Bot"}
    assert result["session"]["pending_command_count"] == 0
