"""Tests for Pokemon Showdown learning signal analysis."""

from app.services.pokemon.showdown_analysis import PokemonShowdownAnalysisService


def test_showdown_analysis_summarizes_result_and_reward():
    service = PokemonShowdownAnalysisService()

    summary = service.summarize(
        [
            {"room_id": "battle-gen9-1", "event_type": "player", "args": ["p1", "Bot"]},
            {"room_id": "battle-gen9-1", "event_type": "player", "args": ["p2", "Rival"]},
            {"room_id": "battle-gen9-1", "event_type": "turn", "args": ["2"]},
            {"room_id": "battle-gen9-1", "event_type": "move", "args": ["p1a: Flutter Mane", "Moonblast", "p2a: Urshifu"]},
            {"room_id": "battle-gen9-1", "event_type": "-damage", "args": ["p2a: Urshifu", "0 fnt"]},
            {"room_id": "battle-gen9-1", "event_type": "faint", "args": ["p2a: Urshifu"]},
            {"room_id": "battle-gen9-1", "event_type": "win", "args": ["Bot"]},
        ],
        decisions=[{"decision_type": "move", "command": "battle-gen9-1|/choose move 1|2"}],
        username="Bot",
    )

    assert summary["status"] == "win"
    assert summary["winner"] == "Bot"
    assert summary["agent_side"] == "p1"
    assert summary["turns"] == 2
    assert summary["moves"] == 1
    assert summary["damage_events"] == 1
    assert summary["faints"] == 1
    assert summary["faints_for"] == 1
    assert summary["faints_against"] == 0
    assert summary["reward"] == 120.0
    assert summary["decision_rewards"] == [
        {
            "index": 0,
            "decision_type": "move",
            "command": "battle-gen9-1|/choose move 1|2",
            "reward": 120.0,
        }
    ]


def test_showdown_analysis_scores_loss_against_agent_side():
    service = PokemonShowdownAnalysisService()

    summary = service.summarize(
        [
            {"event_type": "player", "args": ["p1", "Bot"]},
            {"event_type": "player", "args": ["p2", "Rival"]},
            {"event_type": "faint", "args": ["p1a: Incineroar"]},
            {"event_type": "win", "args": ["Rival"]},
        ],
        username="Bot",
    )

    assert summary["status"] == "loss"
    assert summary["faints_against"] == 1
    assert summary["reward"] == -120.0
