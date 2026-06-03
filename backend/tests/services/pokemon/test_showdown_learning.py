"""Tests for Pokemon Showdown learning profile aggregation."""

from app.services.pokemon.showdown_learning import PokemonShowdownLearningService


def test_showdown_learning_profile_records_completed_sessions_once():
    service = PokemonShowdownLearningService()

    first = service.record_session(
        session_id="s1",
        username="Bot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="balanced",
        analysis={"status": "win", "reward": 120.0, "turns": 4, "faints_for": 1, "faints_against": 0},
        decisions=[{"decision_type": "move"}],
    )
    duplicate = service.record_session(
        session_id="s1",
        username="Bot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="balanced",
        analysis={"status": "win", "reward": 120.0, "turns": 4, "faints_for": 1, "faints_against": 0},
        decisions=[{"decision_type": "move"}],
    )

    assert first["battles"] == 1
    assert duplicate["battles"] == 1
    assert duplicate["wins"] == 1
    assert duplicate["win_rate"] == 1.0
    assert duplicate["average_reward"] == 120.0
    assert duplicate["modes"]["balanced"]["average_reward"] == 120.0
    assert duplicate["decision_types"]["move"]["count"] == 1
    assert duplicate["recommendation"]["mode"] == "balanced"


def test_showdown_learning_profile_ignores_in_progress_sessions():
    service = PokemonShowdownLearningService()

    profile = service.record_session(
        session_id="s2",
        username="Bot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="aggressive",
        analysis={"status": "in_progress", "reward": 0.0},
        decisions=[],
    )

    assert profile["battles"] == 0
    assert profile["recommendation"]["mode"] == "balanced"
