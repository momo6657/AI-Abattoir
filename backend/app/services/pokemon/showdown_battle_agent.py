"""Autonomous Pokemon Showdown battle choice planner.

The planner converts structured Showdown requests into `/choose` commands.
It is deliberately deterministic so it can run without a live websocket, LLM,
or external battle state, while still giving the orchestration layer a stable
place to plug in stronger policy scoring later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.pokemon.showdown_connector import (
    PokemonShowdownConnector,
    ShowdownBattleRequest,
    ShowdownEvent,
    pokemon_showdown_connector,
)


@dataclass
class ShowdownChoicePlan:
    room_id: str
    command: str | None
    choices: list[str] = field(default_factory=list)
    choice_details: list[dict[str, Any]] = field(default_factory=list)
    request_id: int | None = None
    decision_type: str = "none"
    reason: str = ""
    needs_choice: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "command": self.command,
            "choices": self.choices,
            "choice_details": self.choice_details,
            "request_id": self.request_id,
            "decision_type": self.decision_type,
            "reason": self.reason,
            "needs_choice": self.needs_choice,
            "warnings": self.warnings,
        }


class PokemonShowdownBattleAgent:
    """Rule-based bridge from Showdown request payloads to legal commands."""

    def __init__(self, connector: PokemonShowdownConnector | None = None):
        self.connector = connector or pokemon_showdown_connector

    def plan_from_payload(
        self,
        payload: str,
        *,
        mode: str = "balanced",
        team_size: int | None = None,
        allow_tera: bool = True,
    ) -> tuple[list[ShowdownEvent], ShowdownBattleRequest | None, ShowdownChoicePlan]:
        events = self.connector.parse_message(payload)
        request = self.connector.parse_battle_request(events)
        return events, request, self.plan(request, mode=mode, team_size=team_size, allow_tera=allow_tera)

    def plan_from_raw_request(
        self,
        raw_request: dict[str, Any],
        room_id: str,
        *,
        mode: str = "balanced",
        team_size: int | None = None,
        allow_tera: bool = True,
    ) -> ShowdownChoicePlan:
        request = ShowdownBattleRequest(
            room_id=room_id,
            request_id=raw_request.get("rqid"),
            active=raw_request.get("active") or [],
            side=raw_request.get("side") or {},
            force_switch=raw_request.get("forceSwitch") or [],
            wait=bool(raw_request.get("wait")),
            raw=raw_request,
        )
        return self.plan(request, mode=mode, team_size=team_size, allow_tera=allow_tera)

    def plan(
        self,
        request: ShowdownBattleRequest | None,
        *,
        mode: str = "balanced",
        team_size: int | None = None,
        allow_tera: bool = True,
    ) -> ShowdownChoicePlan:
        if request is None:
            return ShowdownChoicePlan(
                room_id="",
                command=None,
                decision_type="none",
                reason="No Showdown request event was found.",
            )
        if request.wait:
            return ShowdownChoicePlan(
                room_id=request.room_id,
                command=None,
                request_id=request.request_id,
                decision_type="wait",
                reason="Showdown requested waiting for the opponent or server state.",
                needs_choice=False,
            )
        if request.team_preview:
            return self._plan_team_preview(request, team_size)
        if request.force_switch:
            return self._plan_force_switch(request)
        if request.active:
            return self._plan_moves(request, mode=mode, allow_tera=allow_tera)
        command = self.connector.build_choose_default(request.room_id, request.request_id)
        return ShowdownChoicePlan(
            room_id=request.room_id,
            command=command,
            choices=["default"],
            request_id=request.request_id,
            decision_type="default",
            reason="No active moves or forced switches were available, so default choice was used.",
            needs_choice=True,
        )

    def _plan_team_preview(self, request: ShowdownBattleRequest, team_size: int | None) -> ShowdownChoicePlan:
        pokemon = request.side.get("pokemon") or []
        requested_size = team_size or request.max_team_size or min(4, len(pokemon)) or 1
        slots = [
            index + 1
            for index, member in enumerate(pokemon)
            if not self._is_fainted(member)
        ][:requested_size]
        if not slots:
            slots = list(range(1, requested_size + 1))
        command = self.connector.build_choose_team(request.room_id, slots, request.request_id)
        details = [
            {
                "slot": slot,
                "choice": f"team_slot {slot}",
                "pokemon": self._display_pokemon(pokemon[slot - 1]) if slot - 1 < len(pokemon) else f"slot {slot}",
                "reason": "healthy preview candidate",
            }
            for slot in slots
        ]
        return ShowdownChoicePlan(
            room_id=request.room_id,
            command=command,
            choices=[f"team {''.join(str(slot) for slot in slots)}"],
            choice_details=details,
            request_id=request.request_id,
            decision_type="team_preview",
            reason=f"Selected the first {len(slots)} healthy team slots for preview.",
            needs_choice=True,
        )

    def _plan_force_switch(self, request: ShowdownBattleRequest) -> ShowdownChoicePlan:
        pokemon = request.side.get("pokemon") or []
        used_slots = set()
        choices: list[str] = []
        details: list[dict[str, Any]] = []
        warnings: list[str] = []
        for active_index, forced in enumerate(request.force_switch):
            if not forced:
                choices.append("pass")
                details.append({
                    "active_index": active_index,
                    "choice": "pass",
                    "reason": "slot was not forced to switch",
                })
                continue
            slot = self._next_switch_slot(pokemon, used_slots)
            if slot is None:
                choices.append("pass")
                details.append({
                    "active_index": active_index,
                    "choice": "pass",
                    "reason": "no healthy bench Pokemon available",
                })
                warnings.append("No healthy bench Pokemon was available for a forced switch.")
                continue
            used_slots.add(slot)
            choices.append(f"switch {slot}")
            details.append({
                "active_index": active_index,
                "choice": f"switch {slot}",
                "slot": slot,
                "pokemon": self._display_pokemon(pokemon[slot - 1]) if slot - 1 < len(pokemon) else f"slot {slot}",
                "reason": "healthy non-active bench Pokemon",
            })
        command = self.connector.build_choose_multi(request.room_id, choices, request.request_id)
        return ShowdownChoicePlan(
            room_id=request.room_id,
            command=command,
            choices=choices,
            choice_details=details,
            request_id=request.request_id,
            decision_type="force_switch",
            reason="Selected healthy non-active bench slots for forced switching.",
            needs_choice=True,
            warnings=warnings,
        )

    def _plan_moves(self, request: ShowdownBattleRequest, *, mode: str, allow_tera: bool) -> ShowdownChoicePlan:
        planned = [
            self._move_choice(active_request, mode=mode, allow_tera=allow_tera and index == 0, active_index=index)
            for index, active_request in enumerate(request.active)
        ]
        choices = [choice for choice, _detail in planned]
        details = [detail for _choice, detail in planned]
        command = self.connector.build_choose_multi(request.room_id, choices, request.request_id)
        return ShowdownChoicePlan(
            room_id=request.room_id,
            command=command,
            choices=choices,
            choice_details=details,
            request_id=request.request_id,
            decision_type="move",
            reason="Scored legal moves by damage, utility, spread pressure, mode, and obvious risk.",
            needs_choice=True,
        )

    def _move_choice(
        self,
        active_request: dict[str, Any],
        *,
        mode: str,
        allow_tera: bool,
        active_index: int,
    ) -> tuple[str, dict[str, Any]]:
        moves = active_request.get("moves") or []
        legal_moves = [
            (index + 1, move)
            for index, move in enumerate(moves)
            if not move.get("disabled") and int(move.get("pp", 1) or 0) > 0
        ]
        if not legal_moves:
            return "default", {
                "active_index": active_index,
                "choice": "default",
                "reason": "no legal moves with PP were available",
            }
        scored_moves = [
            (slot, move, *self._score_move(move, mode))
            for slot, move in legal_moves
        ]
        move_slot, move, score, reason = max(scored_moves, key=lambda item: item[2])
        target = self._target_for_move(move)
        modifier = "terastallize" if allow_tera and self._should_terastallize(active_request, move, mode) else None
        target_part = f" {target}" if target is not None else ""
        modifier_part = f" {modifier}" if modifier else ""
        choice = f"move {move_slot}{target_part}{modifier_part}"
        return choice, {
            "active_index": active_index,
            "choice": choice,
            "move_slot": move_slot,
            "move": move.get("id") or move.get("move") or f"move {move_slot}",
            "target": target,
            "modifier": modifier,
            "score": round(score, 2),
            "reason": reason,
            "legal_candidates": [
                {
                    "slot": slot,
                    "move": candidate.get("id") or candidate.get("move") or f"move {slot}",
                    "score": round(candidate_score, 2),
                }
                for slot, candidate, candidate_score, _candidate_reason in sorted(
                    scored_moves,
                    key=lambda item: item[2],
                    reverse=True,
                )
            ],
        }

    def _score_move(self, move: dict[str, Any], mode: str) -> tuple[float, str]:
        move_id = self.connector.to_id(move.get("id") or move.get("move"))
        if move_id in {"protect", "detect", "spikyshield", "kingsshield"}:
            score = 35.0 if mode == "defensive" else 15.0
            return score, f"protective move scored for {mode} mode"
        utility_scores = {
            "fakeout": 90.0,
            "tailwind": 82.0,
            "trickroom": 78.0,
            "spore": 88.0,
            "sleeppowder": 70.0,
            "taunt": 68.0,
            "followme": 74.0,
            "ragepowder": 74.0,
            "willowisp": 64.0,
            "thunderwave": 62.0,
            "encore": 62.0,
        }
        if move_id in utility_scores:
            score = utility_scores[move_id]
            if mode == "defensive":
                score += 6
            if mode == "aggressive" and move_id not in {"fakeout", "spore"}:
                score -= 6
            return score, f"utility move {move_id} matched tactical priority"
        score = float(move.get("basePower") or move.get("power") or 60)
        if move.get("target") in {"allAdjacentFoes", "allAdjacent", "foeSide"}:
            score += 15
        if move_id in {"explosion", "selfdestruct", "mistyexplosion", "finalgambit"}:
            score -= 260
        if move.get("pp") is not None:
            score += min(float(move.get("pp") or 0), 8.0) * 0.25
        if mode == "aggressive":
            score += 10
        return score, f"damage move scored from base power in {mode} mode"

    def _target_for_move(self, move: dict[str, Any]) -> int | None:
        target_type = move.get("target")
        if target_type in {"normal", "any", "adjacentFoe"}:
            return -1
        if target_type in {"adjacentAlly", "allyTeam"}:
            return 1
        return None

    def _should_terastallize(self, active_request: dict[str, Any], move: dict[str, Any], mode: str) -> bool:
        if mode == "defensive":
            return False
        if not active_request.get("canTerastallize"):
            return False
        move_id = self.connector.to_id(move.get("id") or move.get("move"))
        return move_id not in {"protect", "detect", "spikyshield", "kingsshield"}

    def _next_switch_slot(self, pokemon: list[dict[str, Any]], used_slots: set[int]) -> int | None:
        for index, member in enumerate(pokemon):
            slot = index + 1
            if slot in used_slots:
                continue
            if member.get("active"):
                continue
            if self._is_fainted(member):
                continue
            return slot
        return None

    def _is_fainted(self, member: dict[str, Any]) -> bool:
        condition = str(member.get("condition", "")).lower()
        return " fnt" in condition or condition == "0 fnt" or condition.endswith("/0")

    def _display_pokemon(self, member: dict[str, Any]) -> str:
        ident = str(member.get("ident") or member.get("details") or member.get("name") or "Unknown")
        return ident.split(": ", 1)[-1]


pokemon_showdown_battle_agent = PokemonShowdownBattleAgent()
