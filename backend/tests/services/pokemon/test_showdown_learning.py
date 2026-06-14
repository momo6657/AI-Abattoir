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
    assert duplicate["training_plan"]["next_mission_goal"] == "learn"
    assert duplicate["training_plan"]["recommended_mode"] == "balanced"
    assert duplicate["training_plan"]["stage"] == "exploit"
    assert duplicate["training_plan"]["lesson_count"] >= 2
    assert duplicate["training_plan"]["task_count"] >= 1
    lesson_ids = {lesson["id"] for lesson in duplicate["learning_lessons"]}
    assert "winning_baseline" in lesson_ids
    assert "preferred_mode" in lesson_ids
    assert duplicate["training_tasks"][0]["action"] == "start_search"


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
    assert profile["training_plan"]["stage"] == "collect_data"
    assert profile["training_plan"]["next_mission_goal"] == "queue"
    assert profile["learning_lessons"][0]["id"] == "collect_baseline"
    assert profile["training_tasks"][0]["action"] == "research_team"


def test_showdown_learning_profile_training_plan_stabilizes_weak_results():
    service = PokemonShowdownLearningService()

    profile = service.record_session(
        session_id="s3",
        username="Bot",
        battle_format="vgc2024",
        showdown_format="gen9vgc2024regg",
        mode="defensive",
        analysis={"status": "loss", "reward": 20.0, "turns": 5, "faints_for": 0, "faints_against": 2},
        decisions=[{"decision_type": "switch"}, {"decision_type": "switch"}],
    )

    assert profile["training_plan"]["stage"] == "stabilize"
    assert profile["training_plan"]["next_mission_goal"] == "prepare"
    assert profile["training_plan"]["recommended_mode"] == "defensive"
    assert "audit_switch" in profile["training_plan"]["actions"]
    lesson_ids = {lesson["id"] for lesson in profile["learning_lessons"]}
    assert {"outcome_control", "low_reward", "knockout_deficit", "weak_decision"}.issubset(lesson_ids)
    audit_task = next(task for task in profile["training_tasks"] if task["action"] == "audit_switch")
    assert audit_task["priority"] == "high"
