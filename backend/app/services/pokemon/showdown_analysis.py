"""Analysis helpers for Pokemon Showdown protocol event logs."""

from __future__ import annotations

from typing import Any


class PokemonShowdownAnalysisService:
    """Turns Showdown protocol events into learning-oriented battle signals."""

    def summarize(
        self,
        events: list[dict[str, Any]],
        decisions: list[dict[str, Any]] | None = None,
        username: str | None = None,
    ) -> dict[str, Any]:
        decisions = decisions or []
        username_key = self._normalize_user(username)
        player_by_side: dict[str, str] = {}
        user_side: str | None = None
        turns = 0
        moves = 0
        switches = 0
        damage_events = 0
        fainted: list[str] = []
        faints_for = 0
        faints_against = 0
        winner: str | None = None
        result = "in_progress"
        rooms: set[str] = set()

        for event in events:
            event_type = str(event.get("event_type") or event.get("event") or "")
            args = event.get("args") or []
            room_id = event.get("room_id")
            if room_id:
                rooms.add(str(room_id))

            if event_type == "player":
                side = str(args[0]) if len(args) > 0 else ""
                player = str(args[1]) if len(args) > 1 else ""
                if side and player:
                    player_by_side[side] = player
                    if username_key and self._normalize_user(player) == username_key:
                        user_side = side
            elif event_type == "turn":
                turns = max(turns, self._to_int(args[0] if args else None))
            elif event_type == "move":
                moves += 1
            elif event_type in {"switch", "drag"}:
                switches += 1
            elif event_type == "-damage":
                damage_events += 1
            elif event_type == "faint":
                ident = str(args[0]) if args else ""
                if ident:
                    fainted.append(ident)
                    faint_side = self._side_from_ident(ident)
                    if user_side and faint_side:
                        if faint_side == user_side:
                            faints_against += 1
                        else:
                            faints_for += 1
            elif event_type == "win":
                winner = str(args[0]) if args else None
                if winner and username_key:
                    result = "win" if self._normalize_user(winner) == username_key else "loss"
                else:
                    result = "finished"
            elif event_type == "tie":
                result = "tie"

        reward = self._reward(result, faints_for, faints_against)
        decision_rewards = [
            {
                "index": index,
                "decision_type": decision.get("decision_type"),
                "command": decision.get("command"),
                "reward": reward,
            }
            for index, decision in enumerate(decisions)
        ]
        return {
            "status": result,
            "winner": winner,
            "agent_username": username,
            "agent_side": user_side,
            "players": player_by_side,
            "rooms": sorted(rooms),
            "turns": turns,
            "moves": moves,
            "switches": switches,
            "damage_events": damage_events,
            "faints": len(fainted),
            "fainted": fainted,
            "faints_for": faints_for,
            "faints_against": faints_against,
            "reward": reward,
            "decision_count": len(decisions),
            "decision_rewards": decision_rewards,
        }

    def _reward(self, result: str, faints_for: int, faints_against: int) -> float:
        reward = 20.0 * faints_for - 20.0 * faints_against
        if result == "win":
            reward += 100.0
        elif result == "loss":
            reward -= 100.0
        elif result == "tie":
            reward += 10.0
        return reward

    def _side_from_ident(self, ident: str) -> str | None:
        marker = ident.split(":", 1)[0].strip()
        if marker.startswith("p1"):
            return "p1"
        if marker.startswith("p2"):
            return "p2"
        return None

    def _normalize_user(self, username: str | None) -> str | None:
        if username is None:
            return None
        return "".join(ch for ch in username.lower() if ch.isalnum())

    def _to_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


pokemon_showdown_analysis_service = PokemonShowdownAnalysisService()
