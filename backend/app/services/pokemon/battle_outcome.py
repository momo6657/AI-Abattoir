"""Helpers for resolving the persisted Pokemon battle winner contract."""

from __future__ import annotations

from typing import Any


def winner_side(battle: Any) -> int | None:
    """Return 1 or 2 for current records and tolerate legacy agent-id values."""
    winner = getattr(battle, "winner", None)
    if winner in (1, "1"):
        return 1
    if winner in (2, "2"):
        return 2
    if winner is None:
        return None

    winner_key = str(winner)
    if winner_key == str(getattr(battle, "player1_agent_id", "")):
        return 1
    if winner_key == str(getattr(battle, "player2_agent_id", "")):
        return 2
    return None


def winner_agent_id(battle: Any) -> Any | None:
    side = winner_side(battle)
    if side == 1:
        return getattr(battle, "player1_agent_id", None)
    if side == 2:
        return getattr(battle, "player2_agent_id", None)
    return None


def winner_team_id(battle: Any) -> Any | None:
    side = winner_side(battle)
    if side == 1:
        return getattr(battle, "player1_team_id", None)
    if side == 2:
        return getattr(battle, "player2_team_id", None)
    return None


def side_for_agent(battle: Any, agent_id: Any) -> int | None:
    agent_key = str(agent_id)
    if agent_key == str(getattr(battle, "player1_agent_id", "")):
        return 1
    if agent_key == str(getattr(battle, "player2_agent_id", "")):
        return 2
    return None


def did_agent_win(battle: Any, agent_id: Any) -> bool:
    resolved_winner = winner_agent_id(battle)
    return resolved_winner is not None and str(resolved_winner) == str(agent_id)


def did_team_win(battle: Any, team_id: Any) -> bool:
    resolved_team = winner_team_id(battle)
    return resolved_team is not None and str(resolved_team) == str(team_id)
