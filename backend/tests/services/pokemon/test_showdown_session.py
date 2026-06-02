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


@pytest.mark.asyncio
async def test_connect_flushes_pending_commands_to_connector():
    connector = FakeShowdownConnector()
    service = PokemonShowdownSessionService()
    session = service.create_session(username="Bot", team=None, auto_search=True, connector=connector)

    result = await service.connect_session(session.session_id)

    assert connector.connected
    assert result["sent"] == ["|/utm null", "|/search gen9vgc2024regg"]
    assert connector.sent == result["sent"]
    assert result["session"]["sent_log"] == result["sent"]


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
