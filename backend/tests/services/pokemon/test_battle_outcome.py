"""Tests for the persisted Pokemon battle winner contract."""

from types import SimpleNamespace
from uuid import uuid4

from app.services.pokemon.battle_outcome import (
    did_agent_win,
    did_team_win,
    side_for_agent,
    winner_agent_id,
    winner_side,
    winner_team_id,
)


def _battle(winner):
    return SimpleNamespace(
        winner=winner,
        player1_agent_id=uuid4(),
        player2_agent_id=uuid4(),
        player1_team_id=uuid4(),
        player2_team_id=uuid4(),
    )


def test_resolves_integer_winner_side_to_agent_and_team():
    battle = _battle(2)

    assert winner_side(battle) == 2
    assert winner_agent_id(battle) == battle.player2_agent_id
    assert winner_team_id(battle) == battle.player2_team_id
    assert did_agent_win(battle, battle.player2_agent_id)
    assert did_team_win(battle, battle.player2_team_id)


def test_tolerates_legacy_agent_id_winner_values():
    battle = _battle(None)
    battle.winner = str(battle.player1_agent_id)

    assert winner_side(battle) == 1
    assert winner_agent_id(battle) == battle.player1_agent_id
    assert side_for_agent(battle, str(battle.player2_agent_id)) == 2


def test_unknown_or_draw_winner_is_unresolved():
    battle = _battle(None)

    assert winner_side(battle) is None
    assert winner_agent_id(battle) is None
    assert not did_agent_win(battle, battle.player1_agent_id)

    battle.winner = "unknown"
    assert winner_side(battle) is None
