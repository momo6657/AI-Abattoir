"""Tests for Pokemon Phase 2-4 service helpers."""

from types import SimpleNamespace
from uuid import uuid4

from app.models.agent import AgentLevel
from app.services.pokemon.battle_analysis import PokemonBattleAnalysisService
from app.services.pokemon.knowledge_service import PokemonKnowledgeService
from app.services.pokemon.reinforcement_learning import PokemonRLService
from app.services.pokemon.showdown_connector import PokemonShowdownConnector
from app.services.pokemon.team_builder import PokemonTeamBuilder


def test_rl_state_hash_is_stable():
    service = PokemonRLService()
    left = {"turn": 1, "field": {"weather": "rain"}}
    right = {"field": {"weather": "rain"}, "turn": 1}
    assert service.state_hash(left) == service.state_hash(right)


def test_battle_analysis_summary():
    summary = PokemonBattleAnalysisService().summarize([
        {"event": "move", "data": {"attacker": "Charizard", "damage": 30}},
        {"event": "move", "data": {"attacker": "Charizard", "damage": 20}},
        {"event": "faint", "data": {"pokemon": "Blastoise"}},
        {"event": "switch", "data": {"player": 1}},
    ])
    assert summary["mvp"] == "Charizard"
    assert summary["damage_by_attacker"]["Charizard"] == 50
    assert summary["fainted"] == ["Blastoise"]
    assert summary["switches"] == 1


def test_team_builder_selects_by_playstyle():
    builder = PokemonTeamBuilder()
    agent = SimpleNamespace(
        id=uuid4(),
        name="RainBot",
        level=AgentLevel.NOVICE,
        pokemon_playstyle="rain offense",
        pokemon_stats={},
    )
    template = builder.select_template(agent)
    assert "rain" in template["id"]


def test_team_builder_master_adds_tera_types():
    builder = PokemonTeamBuilder()
    agent = SimpleNamespace(
        id=uuid4(),
        name="MasterBot",
        level=AgentLevel.MASTER,
        pokemon_playstyle="",
        pokemon_stats={},
    )
    template = builder.select_template(agent)
    evolved = builder._light_innovation(template["pokemon"], agent)
    assert all("tera_type" in pokemon for pokemon in evolved)


def test_knowledge_query_builder_targets_vgc_sources():
    query = PokemonKnowledgeService()._build_query("species_usage", "Incineroar")
    assert "Incineroar" in query
    assert "VGC" in query
    assert "pokechamdb.com" in query


def test_showdown_parser_tracks_room_events():
    connector = PokemonShowdownConnector()
    events = connector.parse_message(">battle-gen9vgc-1\n|turn|1\n|move|p1a: Flutter Mane|Moonblast|p2a: Urshifu")
    assert events[0].room_id == "battle-gen9vgc-1"
    assert events[0].event_type == "turn"
    assert events[1].event_type == "move"


def test_showdown_message_builders():
    connector = PokemonShowdownConnector()
    assert connector.build_search_message("gen9vgc2024regg") == "|/search gen9vgc2024regg"
    assert connector.build_choose_move("battle-1", 2, 1) == "battle-1|/choose move 2 1"
    assert connector.build_choose_switch("battle-1", 3) == "battle-1|/choose switch 3"
