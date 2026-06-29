"""Tests for the battle replay service."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from app.services.pokemon.battle_replay import (
    PokemonBattleReplayService,
    BattleReplay,
    ReplayTurn,
    ReplayFrame,
)


@pytest.fixture
def service():
    return PokemonBattleReplayService()


class TestDescribeEvent:
    def test_move_event(self, service):
        event = {"turn": 1, "event": "move", "data": {"attacker": "Pikachu", "move": "Thunderbolt", "target": "Charizard"}}
        desc = service._describe_event(event)
        assert "Pikachu" in desc
        assert "Thunderbolt" in desc
        assert "Charizard" in desc

    def test_damage_event(self, service):
        event = {"turn": 2, "event": "damage", "data": {"target": "Pikachu", "damage": 50}}
        desc = service._describe_event(event)
        assert "Pikachu" in desc
        assert "50" in desc

    def test_faint_event(self, service):
        event = {"turn": 3, "event": "faint", "data": {"pokemon": "Charizard"}}
        desc = service._describe_event(event)
        assert "Charizard" in desc

    def test_switch_event(self, service):
        event = {"turn": 4, "event": "switch", "data": {"player": 1, "from": "Pikachu", "to": "Charizard"}}
        desc = service._describe_event(event)
        assert "Pikachu" in desc
        assert "Charizard" in desc

    def test_heal_event(self, service):
        event = {"turn": 5, "event": "heal", "data": {"target": "Pikachu", "amount": 30}}
        desc = service._describe_event(event)
        assert "Pikachu" in desc
        assert "30" in desc

    def test_status_event(self, service):
        event = {"turn": 6, "event": "status", "data": {"target": "Pikachu", "status": "paralysis"}}
        desc = service._describe_event(event)
        assert "Pikachu" in desc

    def test_weather_event(self, service):
        event = {"turn": 7, "event": "weather", "data": {"weather": "rain"}}
        desc = service._describe_event(event)
        assert "rain" in desc

    def test_terastallize_event(self, service):
        event = {"turn": 8, "event": "terastallize", "data": {"pokemon": "Pikachu", "tera_type": "Electric"}}
        desc = service._describe_event(event)
        assert "Pikachu" in desc
        assert "Electric" in desc

    def test_turn_start_event(self, service):
        event = {"turn": 1, "event": "turn_start", "data": {}}
        desc = service._describe_event(event)
        assert "1" in desc

    def test_unknown_event(self, service):
        event = {"turn": 9, "event": "custom_event", "data": {}}
        desc = service._describe_event(event)
        assert "custom_event" in desc


class TestBuildReplay:
    def test_empty_log(self, service):
        battle = MagicMock()
        battle.id = "test-id"
        battle.battle_format = "vgc2024"
        battle.winner = None
        battle.turns = 0
        battle.battle_log = []
        battle.summary = {}

        replay = service.build_replay(battle)
        assert replay.battle_id == "test-id"
        assert replay.format == "vgc2024"
        assert len(replay.turns) == 0
        assert replay.total_turns == 0

    def test_single_turn(self, service):
        battle = MagicMock()
        battle.id = "test-id"
        battle.battle_format = "vgc2024"
        battle.winner = None
        battle.turns = 1
        battle.battle_log = [
            {"turn": 1, "event": "move", "data": {"attacker": "A", "move": "Tackle"}},
            {"turn": 1, "event": "damage", "data": {"target": "B", "damage": 30}},
        ]
        battle.summary = {}

        replay = service.build_replay(battle)
        assert len(replay.turns) == 1
        assert len(replay.turns[0].frames) == 2

    def test_multiple_turns(self, service):
        battle = MagicMock()
        battle.id = "test-id"
        battle.battle_format = "vgc2024"
        battle.winner = "player1"
        battle.turns = 3
        battle.battle_log = [
            {"turn": 1, "event": "move", "data": {"attacker": "A", "move": "Tackle"}},
            {"turn": 2, "event": "move", "data": {"attacker": "B", "move": "Slash"}},
            {"turn": 3, "event": "faint", "data": {"pokemon": "B"}},
        ]
        battle.summary = {}

        replay = service.build_replay(battle)
        assert len(replay.turns) == 3
        assert replay.winner == "player1"

    def test_integer_winner_resolves_to_agent_id(self, service):
        player1_id = uuid4()
        battle = MagicMock()
        battle.id = "test-id"
        battle.battle_format = "gen9ou"
        battle.player1_agent_id = player1_id
        battle.player2_agent_id = uuid4()
        battle.winner = 1
        battle.turns = 0
        battle.battle_log = []
        battle.summary = {}

        replay = service.build_replay(battle)

        assert replay.winner == str(player1_id)
        assert replay.winner_side == 1

    def test_to_dict(self, service):
        battle = MagicMock()
        battle.id = "test-id"
        battle.battle_format = "vgc2024"
        battle.winner = None
        battle.turns = 1
        battle.battle_log = [
            {"turn": 1, "event": "move", "data": {"attacker": "A", "move": "Tackle"}},
        ]
        battle.summary = {}

        replay = service.build_replay(battle)
        d = replay.to_dict()
        assert isinstance(d, dict)
        assert d["battle_id"] == "test-id"
        assert d["winner_side"] is None
        assert len(d["turns"]) == 1
        assert "frames" in d["turns"][0]
