"""Tests for comprehensive team analysis score normalization."""

from app.services.pokemon import comprehensive_analysis as analysis_module
from app.services.pokemon.comprehensive_analysis import PokemonComprehensiveAnalysis


def test_normalizes_named_scores():
    service = PokemonComprehensiveAnalysis()

    assert service._normalize_score("optimal") == 100
    assert service._normalize_score("neutral") == 50
    assert service._normalize_score("suboptimal") == 30
    assert service._normalize_score(140) == 100


def test_missing_optional_build_data_does_not_reduce_score(monkeypatch):
    monkeypatch.setattr(
        analysis_module.pokemon_move_analysis,
        "analyze_moveset",
        lambda moves, types: {"score": 80, "coverage": []},
    )
    service = PokemonComprehensiveAnalysis()

    result = service.analyze_pokemon(
        {"species": "Testmon", "types": ["Fire"], "moves": ["Protect"]}
    )

    assert result["overall_score"] == 80
    assert result["analyses"]["ability"] is None
    assert result["analyses"]["nature"] is None
    assert result["analyses"]["evs"] is None
    assert result["analyses"]["tera"] is None
    assert result["data_completeness"]["evs"] is False
    assert result["data_completeness"]["tera_type"] is False
