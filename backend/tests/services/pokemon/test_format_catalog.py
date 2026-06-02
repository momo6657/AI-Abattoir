"""Tests for Pokemon battle format catalog."""

import pytest

from app.services.pokemon.format_catalog import PokemonFormatCatalog


def test_format_catalog_resolves_internal_alias_and_showdown_id():
    catalog = PokemonFormatCatalog()

    assert catalog.get("vgc").id == "vgc2024"
    assert catalog.get("gen9vgc2024regg").id == "vgc2024"
    assert catalog.showdown_format("vgc2024") == "gen9vgc2024regg"


def test_format_catalog_describes_random_battle_as_no_team():
    catalog = PokemonFormatCatalog()

    battle_format = catalog.get("random")

    assert battle_format.id == "gen9randombattle"
    assert battle_format.showdown_format == "gen9randombattle"
    assert not battle_format.requires_team
    assert battle_format.active_pokemon == 1


def test_template_format_requires_configured_templates():
    catalog = PokemonFormatCatalog()

    assert catalog.template_format("gen9vgc2024regg") == "vgc2024"
    with pytest.raises(ValueError):
        catalog.template_format("gen9ou")
