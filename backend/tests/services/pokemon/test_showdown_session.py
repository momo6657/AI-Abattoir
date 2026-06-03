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

    refreshed = service.analyze_session(session.session_id)
    assert refreshed == analysis
    profile = service.learning_profile("Bot", "vgc2024")
    assert profile["battles"] == 1
    assert profile["recommendation"]["mode"] == "balanced"


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


def test_create_singles_session_auto_generates_showdown_team():
    service = PokemonShowdownSessionService()

    session = service.create_session(username="Bot", team=None, battle_format="gen9ou", auto_search=True)

    assert session.battle_format == "gen9ou"
    assert session.showdown_format == "gen9ou"
    assert session.team_source == "showdown_factory"
    assert session.team_species == ["Great Tusk", "Kingambit", "Gholdengo", "Dragapult", "Iron Valiant", "Ting-Lu"]
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
