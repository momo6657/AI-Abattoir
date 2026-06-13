"""Tests for autonomous Pokemon Showdown team generation."""

from app.services.pokemon.showdown_connector import PokemonShowdownConnector
from app.services.pokemon.showdown_team_factory import pokemon_showdown_team_factory


def test_generate_vgc_team_from_local_template():
    generated = pokemon_showdown_team_factory.generate("vgc2024", mode="balanced")

    assert generated is not None
    assert generated.source == "template"
    assert len(generated.team) == 4
    assert generated.species()


def test_generate_singles_showdown_team_for_ou():
    generated = pokemon_showdown_team_factory.generate("gen9ou", mode="balanced")

    assert generated is not None
    assert generated.source == "showdown_factory"
    assert len(generated.team) == 6
    assert generated.species()[0] == "Great Tusk"
    assert all(member["level"] == 100 for member in generated.team)

    packed = PokemonShowdownConnector().pack_team(generated.team)
    assert packed.startswith("Great Tusk||boosterenergy|protosynthesis|")
    assert "|50|" not in packed
    assert generated.audit["status"] in {"passed", "warning"}
    assert "entry_hazards" in generated.audit["covered_priorities"]
    assert "hazard_removal" in generated.audit["covered_priorities"]
    assert any(member["species"] == "Great Tusk" for member in generated.audit["member_roles"])


def test_generate_doubles_showdown_team_for_doubles_ou():
    generated = pokemon_showdown_team_factory.generate("gen9doublesou", mode="balanced")

    assert generated is not None
    assert generated.source == "showdown_factory"
    assert len(generated.team) == 6
    assert "Incineroar" in generated.species()
    assert all(member["level"] == 100 for member in generated.team)
    assert generated.audit["score"] > 0
    assert "fake_out_pressure" in generated.audit["covered_priorities"]
    assert "speed_control" in generated.audit["covered_priorities"]


def test_random_battle_does_not_generate_team():
    assert pokemon_showdown_team_factory.generate("random", mode="balanced") is None
