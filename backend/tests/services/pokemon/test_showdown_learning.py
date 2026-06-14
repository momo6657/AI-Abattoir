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
    assert duplicate["policy_evaluation"]["phase"] == "explore"
    assert duplicate["policy_evaluation"]["policy"] == "explore_under_sampled_mode"
    assert duplicate["policy_evaluation"]["recommended_mode"] == "aggressive"
    assert duplicate["policy_evaluation"]["next_experiment"]["mission_goal"] == "ladder"
    assert duplicate["training_plan"]["next_mission_goal"] == "learn"
    assert duplicate["training_plan"]["recommended_mode"] == "balanced"
    assert duplicate["training_plan"]["stage"] == "exploit"
    assert duplicate["training_plan"]["policy_phase"] == "explore"
    assert duplicate["training_plan"]["policy_confidence"] == "low"
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
    assert profile["policy_evaluation"]["phase"] == "collect_data"
    assert profile["policy_evaluation"]["recommended_mode"] == "balanced"
    assert profile["policy_evaluation"]["next_experiment"]["mission_goal"] == "queue"
    assert profile["training_plan"]["stage"] == "collect_data"
    assert profile["training_plan"]["policy_phase"] == "collect_data"
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
    assert profile["policy_evaluation"]["phase"] == "stabilize"
    assert profile["policy_evaluation"]["risk"] == "high"
    assert profile["training_plan"]["policy_phase"] == "stabilize"
    assert "audit_switch" in profile["training_plan"]["actions"]
    lesson_ids = {lesson["id"] for lesson in profile["learning_lessons"]}
    assert {"outcome_control", "low_reward", "knockout_deficit", "weak_decision"}.issubset(lesson_ids)
    audit_task = next(task for task in profile["training_tasks"] if task["action"] == "audit_switch")
    assert audit_task["priority"] == "high"


def test_showdown_learning_policy_evaluation_exploits_sampled_modes():
    service = PokemonShowdownLearningService()
    samples = [
        ("balanced", 90.0),
        ("balanced", 95.0),
        ("balanced", 100.0),
        ("aggressive", 130.0),
        ("aggressive", 140.0),
        ("aggressive", 135.0),
        ("defensive", 80.0),
        ("defensive", 85.0),
        ("defensive", 90.0),
    ]

    profile = {}
    for index, (mode, reward) in enumerate(samples):
        profile = service.record_session(
            session_id=f"sampled-{index}",
            username="Bot",
            battle_format="vgc2024",
            showdown_format="gen9vgc2024regg",
            mode=mode,
            analysis={"status": "win", "reward": reward, "turns": 4, "faints_for": 2, "faints_against": 0},
            decisions=[{"decision_type": "move"}],
        )

    policy = profile["policy_evaluation"]
    assert policy["phase"] == "exploit"
    assert policy["policy"] == "exploit_best_mode"
    assert policy["recommended_mode"] == "aggressive"
    assert policy["confidence"] == "high"
    assert policy["exploration_required"] is False
    assert policy["next_experiment"]["mission_goal"] == "learn"
    assert profile["training_plan"]["policy_phase"] == "exploit"
