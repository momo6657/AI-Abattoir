"""In-memory learning profile for Pokemon Showdown sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShowdownLearningProfile:
    username: str
    battle_format: str
    showdown_format: str
    battles: int = 0
    wins: int = 0
    losses: int = 0
    ties: int = 0
    total_reward: float = 0.0
    total_turns: int = 0
    total_faints_for: int = 0
    total_faints_against: int = 0
    modes: dict[str, dict[str, Any]] = field(default_factory=dict)
    decision_types: dict[str, dict[str, Any]] = field(default_factory=dict)
    recent_sessions: list[dict[str, Any]] = field(default_factory=list)
    recorded_sessions: set[str] = field(default_factory=set)

    def record(
        self,
        *,
        session_id: str,
        mode: str,
        analysis: dict[str, Any],
        decisions: list[dict[str, Any]],
    ) -> None:
        if session_id in self.recorded_sessions:
            return

        status = str(analysis.get("status") or "in_progress")
        reward = float(analysis.get("reward") or 0.0)
        self.recorded_sessions.add(session_id)
        self.battles += 1
        self.total_reward += reward
        self.total_turns += int(analysis.get("turns") or 0)
        self.total_faints_for += int(analysis.get("faints_for") or 0)
        self.total_faints_against += int(analysis.get("faints_against") or 0)
        if status == "win":
            self.wins += 1
        elif status == "loss":
            self.losses += 1
        elif status == "tie":
            self.ties += 1

        mode_stats = self.modes.setdefault(mode, {"battles": 0, "wins": 0, "total_reward": 0.0})
        mode_stats["battles"] += 1
        mode_stats["total_reward"] += reward
        if status == "win":
            mode_stats["wins"] += 1

        for decision in decisions:
            decision_type = str(decision.get("decision_type") or "unknown")
            decision_stats = self.decision_types.setdefault(
                decision_type,
                {"count": 0, "total_reward": 0.0},
            )
            decision_stats["count"] += 1
            decision_stats["total_reward"] += reward

        self.recent_sessions.insert(
            0,
            {
                "session_id": session_id,
                "status": status,
                "reward": reward,
                "turns": analysis.get("turns", 0),
                "mode": mode,
            },
        )
        self.recent_sessions = self.recent_sessions[:10]

    def to_dict(self) -> dict[str, Any]:
        battles = max(self.battles, 1)
        mode_summaries = {
            mode: {
                **stats,
                "average_reward": stats["total_reward"] / max(stats["battles"], 1),
                "win_rate": stats["wins"] / max(stats["battles"], 1),
            }
            for mode, stats in self.modes.items()
        }
        decision_summaries = {
            decision_type: {
                **stats,
                "average_reward": stats["total_reward"] / max(stats["count"], 1),
            }
            for decision_type, stats in self.decision_types.items()
        }
        return {
            "username": self.username,
            "battle_format": self.battle_format,
            "showdown_format": self.showdown_format,
            "battles": self.battles,
            "wins": self.wins,
            "losses": self.losses,
            "ties": self.ties,
            "win_rate": self.wins / battles if self.battles else 0.0,
            "average_reward": self.total_reward / battles if self.battles else 0.0,
            "average_turns": self.total_turns / battles if self.battles else 0.0,
            "faints_for": self.total_faints_for,
            "faints_against": self.total_faints_against,
            "modes": mode_summaries,
            "decision_types": decision_summaries,
            "recommendation": self._recommendation(mode_summaries),
            "training_focus": self._training_focus(mode_summaries, decision_summaries),
            "training_plan": self._training_plan(mode_summaries, decision_summaries),
            "recent_sessions": self.recent_sessions,
        }

    def _recommendation(self, mode_summaries: dict[str, dict[str, Any]]) -> dict[str, str]:
        if not mode_summaries:
            return {"mode": "balanced", "reason": "No completed Showdown battles have been learned yet."}
        best_mode, stats = max(
            mode_summaries.items(),
            key=lambda item: (item[1]["average_reward"], item[1]["win_rate"], item[1]["battles"]),
        )
        return {
            "mode": best_mode,
            "reason": (
                f"{best_mode} has the best observed average reward "
                f"({stats['average_reward']:.1f}) across {stats['battles']} battle(s)."
            ),
        }

    def _training_focus(
        self,
        mode_summaries: dict[str, dict[str, Any]],
        decision_summaries: dict[str, dict[str, Any]],
    ) -> list[dict[str, str]]:
        if not self.battles:
            return [
                {
                    "level": "info",
                    "title": "Collect Showdown battle data",
                    "detail": "Run completed Showdown battles so the agent can compare modes, rewards, and decision outcomes.",
                }
            ]

        focus: list[dict[str, str]] = []
        win_rate = self.wins / max(self.battles, 1)
        average_reward = self.total_reward / max(self.battles, 1)

        if win_rate < 0.5:
            focus.append(
                {
                    "level": "warning",
                    "title": "Stabilize match outcomes",
                    "detail": "Win rate is below 50%; prefer safer positioning, protect turns, and knowledge-backed move choices.",
                }
            )
        if self.total_faints_against > self.total_faints_for:
            focus.append(
                {
                    "level": "warning",
                    "title": "Reduce knockout deficit",
                    "detail": "The agent is losing more Pokemon than it removes; review switch and defensive choices before laddering further.",
                }
            )
        if average_reward < 50:
            focus.append(
                {
                    "level": "warning",
                    "title": "Improve reward baseline",
                    "detail": "Average reward is low; run team research and compare battle modes before committing to long auto-runs.",
                }
            )

        weakest_mode = self._weakest_mode(mode_summaries)
        if weakest_mode:
            focus.append(
                {
                    "level": "info",
                    "title": f"Re-test {weakest_mode} mode",
                    "detail": "This mode has the weakest observed reward; collect more samples or avoid it until team matchups improve.",
                }
            )

        weakest_decision = self._weakest_decision(decision_summaries)
        if weakest_decision:
            focus.append(
                {
                    "level": "info",
                    "title": f"Audit {weakest_decision} decisions",
                    "detail": "This decision type has the lowest average reward contribution across recorded battles.",
                }
            )

        if not focus:
            focus.append(
                {
                    "level": "success",
                    "title": "Maintain current training loop",
                    "detail": "Current Showdown results are stable; continue bounded auto-runs and expand samples across formats.",
                }
            )
        return focus[:5]

    def _training_plan(
        self,
        mode_summaries: dict[str, dict[str, Any]],
        decision_summaries: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        recommendation = self._recommendation(mode_summaries)
        recommended_mode = recommendation["mode"]
        weakest_decision = self._weakest_decision(decision_summaries)
        win_rate = self.wins / max(self.battles, 1) if self.battles else 0.0
        average_reward = self.total_reward / max(self.battles, 1) if self.battles else 0.0
        faint_delta = self.total_faints_for - self.total_faints_against

        if not self.battles:
            return {
                "stage": "collect_data",
                "next_mission_goal": "queue",
                "recommended_mode": "balanced",
                "confidence": "low",
                "actions": ["research_team", "start_search", "autopilot", "analyze"],
                "stop_condition": "Stop after the first completed battle summary is available.",
                "reason": "No completed Showdown battles are recorded, so the agent should gather a baseline sample.",
            }

        if win_rate < 0.45 or average_reward < 40 or faint_delta < 0:
            actions = ["research_team", "plan_adjustments", "queue_short_run", "analyze"]
            if weakest_decision:
                actions.insert(1, f"audit_{weakest_decision}")
            return {
                "stage": "stabilize",
                "next_mission_goal": "prepare",
                "recommended_mode": recommended_mode,
                "confidence": "medium" if self.battles >= 3 else "low",
                "actions": actions,
                "stop_condition": "Stop after team research and one bounded battle review.",
                "reason": "Recent learning signals are weak; prioritize knowledge-backed adjustments before longer ladder runs.",
            }

        if win_rate >= 0.6 and average_reward >= 70:
            return {
                "stage": "exploit",
                "next_mission_goal": "learn",
                "recommended_mode": recommended_mode,
                "confidence": "high" if self.battles >= 5 else "medium",
                "actions": ["start_search", "autopilot", "analyze", "new_session"],
                "stop_condition": "Continue bounded runs while reward and win rate remain stable.",
                "reason": "The profile is performing well enough to collect more ladder samples and reinforce successful choices.",
            }

        return {
            "stage": "improve",
            "next_mission_goal": "ladder",
            "recommended_mode": recommended_mode,
            "confidence": "medium" if self.battles >= 3 else "low",
            "actions": ["research_team", "start_search", "autopilot", "analyze"],
            "stop_condition": "Stop after each battle to refresh learning and review decision rewards.",
            "reason": "The profile has usable data but still needs controlled samples to improve mode and decision estimates.",
        }

    def _weakest_mode(self, mode_summaries: dict[str, dict[str, Any]]) -> str | None:
        if len(mode_summaries) < 2:
            return None
        mode, stats = min(
            mode_summaries.items(),
            key=lambda item: (item[1]["average_reward"], item[1]["win_rate"], -item[1]["battles"]),
        )
        return mode if stats["average_reward"] < 50 else None

    def _weakest_decision(self, decision_summaries: dict[str, dict[str, Any]]) -> str | None:
        if not decision_summaries:
            return None
        decision_type, stats = min(
            decision_summaries.items(),
            key=lambda item: (item[1]["average_reward"], -item[1]["count"]),
        )
        return decision_type if stats["count"] >= 2 and stats["average_reward"] < 50 else None


class PokemonShowdownLearningService:
    """Aggregates completed Showdown session results into per-format profiles."""

    def __init__(self):
        self.profiles: dict[tuple[str, str], ShowdownLearningProfile] = {}

    def record_session(
        self,
        *,
        session_id: str,
        username: str,
        battle_format: str,
        showdown_format: str,
        mode: str,
        analysis: dict[str, Any],
        decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        status = analysis.get("status")
        if status not in {"win", "loss", "tie", "finished"}:
            return self.profile(username=username, battle_format=battle_format)
        key = (self._normalize(username), battle_format)
        profile = self.profiles.setdefault(
            key,
            ShowdownLearningProfile(
                username=username,
                battle_format=battle_format,
                showdown_format=showdown_format,
            ),
        )
        profile.record(session_id=session_id, mode=mode, analysis=analysis, decisions=decisions)
        return profile.to_dict()

    def profile(self, username: str, battle_format: str) -> dict[str, Any]:
        key = (self._normalize(username), battle_format)
        profile = self.profiles.get(key)
        if profile is None:
            return ShowdownLearningProfile(
                username=username,
                battle_format=battle_format,
                showdown_format=battle_format,
            ).to_dict()
        return profile.to_dict()

    def list_profiles(self) -> list[dict[str, Any]]:
        return [profile.to_dict() for profile in self.profiles.values()]

    def _normalize(self, username: str) -> str:
        return "".join(ch for ch in username.lower() if ch.isalnum())


pokemon_showdown_learning_service = PokemonShowdownLearningService()
