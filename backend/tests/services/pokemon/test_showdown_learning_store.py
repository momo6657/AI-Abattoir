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
    assert profile["policy_evaluation"]["phase"] == "explore"
    assert profile["policy_evaluation"]["policy"] == "explore_under_sampled_mode"
    assert profile["training_plan"]["policy_phase"] == "explore"
    assert profile["training_focus"][0]["level"] == "success"
    assert {lesson["id"] for lesson in profile["learning_lessons"]} >= {"winning_baseline", "preferred_mode"}
    assert profile["training_tasks"][0]["action"] == "start_search"

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
    assert duplicate["policy_evaluation"]["exploration_required"] is True

    profiles = await pokemon_showdown_learning_store.list_profiles(db)
    assert len(profiles) == 1
    assert profiles[0]["username"] == "Bot"


@pytest.mark.asyncio
async def test_showdown_learning_store_returns_training_focus_for_weak_results(setup_db, db):
    for index in range(2):
        profile = await pokemon_showdown_learning_store.record_session(
            db,
            session_id=f"weak-session-{index}",
            username="Bot",
            battle_format="gen9ou",
            showdown_format="gen9ou",
            mode="aggressive" if index == 0 else "defensive",
            analysis={
                "status": "loss",
                "reward": 20.0,
                "turns": 4,
                "faints_for": 1,
                "faints_against": 3,
            },
            decisions=[{"decision_type": "move"}],
        )

    focus_titles = [item["title"] for item in profile["training_focus"]]

    assert profile["losses"] == 2
    assert profile["win_rate"] == 0.0
    assert profile["policy_evaluation"]["phase"] == "stabilize"
    assert profile["policy_evaluation"]["risk"] == "high"
    assert "Stabilize match outcomes" in focus_titles
    assert "Reduce knockout deficit" in focus_titles
    assert "Improve reward baseline" in focus_titles
    assert "Audit move decisions" in focus_titles
    lesson_ids = {lesson["id"] for lesson in profile["learning_lessons"]}
    assert {"outcome_control", "low_reward", "knockout_deficit", "weak_decision"}.issubset(lesson_ids)
    assert any(task["action"] == "audit_move" and task["priority"] == "high" for task in profile["training_tasks"])


@pytest.mark.asyncio
async def test_showdown_learning_store_ranks_mastery_profiles(setup_db, db):
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="mastery-strong-1",
        username="StrongBot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="balanced",
        analysis={"status": "win", "reward": 140.0, "turns": 4, "faints_for": 3, "faints_against": 0},
        decisions=[{"decision_type": "move"}],
    )
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="mastery-weak-1",
        username="WeakBot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="balanced",
        analysis={"status": "loss", "reward": 10.0, "turns": 4, "faints_for": 0, "faints_against": 3},
        decisions=[{"decision_type": "move"}],
    )
    await pokemon_showdown_learning_store.record_session(
        db,
        session_id="mastery-ou-1",
        username="OuBot",
        battle_format="gen9ou",
        showdown_format="gen9ou",
        mode="balanced",
        analysis={"status": "win", "reward": 150.0, "turns": 4, "faints_for": 2, "faints_against": 0},
        decisions=[{"decision_type": "move"}],
    )

    ranking = await pokemon_showdown_learning_store.mastery_ranking(db, battle_format="vgc2024", limit=2)

    assert [entry["username"] for entry in ranking] == ["StrongBot", "WeakBot"]
    assert ranking[0]["rank"] == 1
    assert ranking[0]["mastery_score"] > ranking[1]["mastery_score"]
    assert all(entry["battle_format"] == "vgc2024" for entry in ranking)
