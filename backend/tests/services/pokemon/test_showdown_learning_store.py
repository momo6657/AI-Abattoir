"""Tests for database-backed Pokemon Showdown learning records."""

import pytest

from app.services.pokemon.showdown_learning_store import pokemon_showdown_learning_store


@pytest.mark.asyncio
async def test_showdown_learning_store_persists_and_aggregates(setup_db, db):
    profile = await pokemon_showdown_learning_store.record_session(
        db,
        session_id="store-session-1",
        username="Bot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="aggressive",
        analysis={"status": "win", "reward": 130.0, "turns": 5, "faints_for": 2, "faints_against": 1},
        decisions=[{"decision_type": "move"}, {"decision_type": "switch"}],
    )

    assert profile["battles"] == 1
    assert profile["wins"] == 1
    assert profile["average_reward"] == 130.0
    assert profile["recommendation"]["mode"] == "aggressive"

    duplicate = await pokemon_showdown_learning_store.record_session(
        db,
        session_id="store-session-1",
        username="Bot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="aggressive",
        analysis={"status": "win", "reward": 130.0, "turns": 5, "faints_for": 2, "faints_against": 1},
        decisions=[{"decision_type": "move"}, {"decision_type": "switch"}],
    )

    assert duplicate["battles"] == 1
    assert duplicate["decision_types"]["move"]["count"] == 1

    profiles = await pokemon_showdown_learning_store.list_profiles(db)
    assert len(profiles) == 1
    assert profiles[0]["username"] == "Bot"
