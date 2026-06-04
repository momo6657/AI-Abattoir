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
        active_pokemon: int | None = None,
        allow_tera: bool = True,
        knowledge_context: dict[str, Any] | None = None,
        learning_profile: dict[str, Any] | None = None,
        team_context: list[dict[str, Any]] | None = None,
    ) -> tuple[list[ShowdownEvent], ShowdownBattleRequest | None, ShowdownChoicePlan]:
        events = self.connector.parse_message(payload)
        request = self.connector.parse_battle_request(events)
        return events, request, self.plan(
            request,
            mode=mode,
            team_size=team_size,
            active_pokemon=active_pokemon,
            allow_tera=allow_tera,
            knowledge_context=knowledge_context,
            learning_profile=learning_profile,
            team_context=team_context,
        )

    def plan_from_raw_request(
        self,
        raw_request: dict[str, Any],
        room_id: str,
        *,
        mode: str = "balanced",
        team_size: int | None = None,
        active_pokemon: int | None = None,
        allow_tera: bool = True,
        knowledge_context: dict[str, Any] | None = None,
        learning_profile: dict[str, Any] | None = None,
        team_context: list[dict[str, Any]] | None = None,
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
        return self.plan(
            request,
            mode=mode,
            team_size=team_size,
            active_pokemon=active_pokemon,
            allow_tera=allow_tera,
            knowledge_context=knowledge_context,
            learning_profile=learning_profile,
            team_context=team_context,
        )

    def plan(
        self,
        request: ShowdownBattleRequest | None,
        *,
        mode: str = "balanced",
        team_size: int | None = None,
        active_pokemon: int | None = None,
        allow_tera: bool = True,
        knowledge_context: dict[str, Any] | None = None,
        learning_profile: dict[str, Any] | None = None,
        team_context: list[dict[str, Any]] | None = None,
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
            return self._plan_team_preview(
                request,
                team_size,
                mode=mode,
                knowledge_context=knowledge_context,
                learning_profile=learning_profile,
                team_context=team_context,
            )
        if request.force_switch:
            return self._plan_force_switch(request)
        if request.active:
            return self._plan_moves(
                request,
                mode=mode,
                active_pokemon=active_pokemon,
                allow_tera=allow_tera,
                knowledge_context=knowledge_context,
                learning_profile=learning_profile,
            )
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

    def _plan_team_preview(
        self,
        request: ShowdownBattleRequest,
        team_size: int | None,
        *,
        mode: str,
        knowledge_context: dict[str, Any] | None,
        learning_profile: dict[str, Any] | None,
        team_context: list[dict[str, Any]] | None,
    ) -> ShowdownChoicePlan:
        pokemon = request.side.get("pokemon") or []
        requested_size = team_size or request.max_team_size or min(4, len(pokemon)) or 1
        candidates = [
            self._preview_candidate(
                index + 1,
                member,
                mode=mode,
                knowledge_context=knowledge_context,
                learning_profile=learning_profile,
                team_context=team_context,
            )
            for index, member in enumerate(pokemon)
            if not self._is_fainted(member)
        ]
        ranked = sorted(candidates, key=lambda item: (-item["score"], item["slot"]))
        selected = ranked[:requested_size]
        slots = [int(candidate["slot"]) for candidate in selected]
        if not slots:
            slots = list(range(1, requested_size + 1))
        command = self.connector.build_choose_team(request.room_id, slots, request.request_id)
        details = selected or [
            {
                "slot": slot,
                "choice": f"team_slot {slot}",
                "pokemon": self._display_pokemon(pokemon[slot - 1]) if slot - 1 < len(pokemon) else f"slot {slot}",
                "score": 0.0,
                "reason": "fallback team preview slot",
            }
            for slot in slots
        ]
        reason = f"Selected {len(slots)} healthy team slots for preview."
        if any(detail.get("strategy_used") for detail in details):
            reason = f"{reason} Lead order was scored from team roles, mode, knowledge, and learning profile."
        return ShowdownChoicePlan(
            room_id=request.room_id,
            command=command,
            choices=[f"team {''.join(str(slot) for slot in slots)}"],
            choice_details=details,
            request_id=request.request_id,
            decision_type="team_preview",
            reason=reason,
            needs_choice=True,
        )

    def _preview_candidate(
        self,
        slot: int,
        member: dict[str, Any],
        *,
        mode: str,
        knowledge_context: dict[str, Any] | None,
        learning_profile: dict[str, Any] | None,
        team_context: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        pokemon_name = self._display_pokemon(member)
        team_member = self._team_member_for_slot(slot, pokemon_name, team_context)
        score, reasons = self._score_preview_candidate(
            pokemon_name,
            team_member,
            mode=mode,
            knowledge_context=knowledge_context,
            learning_profile=learning_profile,
        )
        return {
            "slot": slot,
            "choice": f"team_slot {slot}",
            "pokemon": pokemon_name,
            "score": round(score, 2),
            "reason": "; ".join(reasons) if reasons else "healthy preview candidate",
            "strategy_used": bool(reasons),
            "knowledge_used": any("knowledge context" in reason for reason in reasons),
            "learning_used": any("learning profile" in reason for reason in reasons),
        }

    def _score_preview_candidate(
        self,
        pokemon_name: str,
        team_member: dict[str, Any] | None,
        *,
        mode: str,
        knowledge_context: dict[str, Any] | None,
        learning_profile: dict[str, Any] | None,
    ) -> tuple[float, list[str]]:
        score = 50.0
        reasons: list[str] = []
        moves = {self.connector.to_id(move) for move in self._member_moves(team_member)}
        ability = self.connector.to_id((team_member or {}).get("ability"))
        item = self.connector.to_id((team_member or {}).get("item"))

        if "fakeout" in moves:
            score += 35
            reasons.append("Fake Out pressure is valuable from lead")
        if moves & {"tailwind", "trickroom"}:
            score += 30
            reasons.append("speed control can shape turn one")
        if moves & {"followme", "ragepowder"}:
            score += 24
            reasons.append("redirection protects setup partners")
        if ability == "intimidate":
            score += 16
            reasons.append("Intimidate improves opening positioning")
        if moves & {"spore", "sleeppowder", "taunt"}:
            score += 12
            reasons.append("disruption move is useful early")
        if mode == "aggressive" and moves & {"fakeout", "spore", "sleeppowder", "taunt"}:
            score += 8
            reasons.append("aggressive mode favors immediate disruption")
        if mode == "defensive" and (ability == "intimidate" or moves & {"protect", "snarl", "partingshot"}):
            score += 8
            reasons.append("defensive mode favors safer opening roles")
        if self._needs_safer_play(learning_profile):
            if "protect" in moves:
                score += 14
                reasons.append("learning profile favors Protect-capable leads")
            if ability == "intimidate" or item in {"sitrusberry", "focussash"}:
                score += 6
                reasons.append("learning profile favors stable lead resources")
        knowledge_bonus, knowledge_reason = self._knowledge_preview_bonus(pokemon_name, knowledge_context)
        if knowledge_bonus:
            score += knowledge_bonus
            reasons.append(knowledge_reason)
        return score, reasons

    def _team_member_for_slot(
        self,
        slot: int,
        pokemon_name: str,
        team_context: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        if not team_context:
            return None
        if 0 <= slot - 1 < len(team_context):
            return team_context[slot - 1]
        pokemon_id = self.connector.to_id(pokemon_name)
        for member in team_context:
            member_id = self.connector.to_id(member.get("species") or member.get("name"))
            if member_id and (member_id == pokemon_id or member_id in pokemon_id or pokemon_id in member_id):
                return member
        return None

    def _member_moves(self, member: dict[str, Any] | None) -> list[str]:
        moves = (member or {}).get("moves") or []
        return [str(move.get("name") if isinstance(move, dict) else move) for move in moves]

    def _knowledge_preview_bonus(
        self,
        pokemon_name: str,
        knowledge_context: dict[str, Any] | None,
    ) -> tuple[float, str]:
        if not knowledge_context or self._knowledge_member_for_pokemon(pokemon_name, knowledge_context) is None:
            return 0.0, ""
        return 8.0, "knowledge context is available for this lead"

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

    def _plan_moves(
        self,
        request: ShowdownBattleRequest,
        *,
        mode: str,
        active_pokemon: int | None,
        allow_tera: bool,
        knowledge_context: dict[str, Any] | None,
        learning_profile: dict[str, Any] | None,
    ) -> ShowdownChoicePlan:
        active_species = self._active_species(request)
        planned = [
            self._move_choice(
                active_request,
                mode=mode,
                allow_tera=allow_tera and index == 0,
                active_index=index,
                active_pokemon=active_pokemon,
                pokemon_name=active_species[index] if index < len(active_species) else "",
                knowledge_context=knowledge_context,
                learning_profile=learning_profile,
            )
            for index, active_request in enumerate(request.active)
        ]
        choices = [choice for choice, _detail in planned]
        details = [detail for _choice, detail in planned]
        command = self.connector.build_choose_multi(request.room_id, choices, request.request_id)
        reason = "Scored legal moves by damage, utility, spread pressure, mode, and obvious risk."
        if any(detail.get("learning_used") for detail in details):
            reason = f"{reason} Learning profile nudged the plan toward safer play."
        return ShowdownChoicePlan(
            room_id=request.room_id,
            command=command,
            choices=choices,
            choice_details=details,
            request_id=request.request_id,
            decision_type="move",
            reason=reason,
            needs_choice=True,
        )

    def _move_choice(
        self,
        active_request: dict[str, Any],
        *,
        mode: str,
        allow_tera: bool,
        active_index: int,
        active_pokemon: int | None,
        pokemon_name: str,
        knowledge_context: dict[str, Any] | None,
        learning_profile: dict[str, Any] | None,
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
            (slot, move, *self._score_move(move, mode, pokemon_name, knowledge_context, learning_profile))
            for slot, move in legal_moves
        ]
        move_slot, move, score, reason = max(scored_moves, key=lambda item: item[2])
        target = self._target_for_move(move, active_pokemon)
        modifier = "terastallize" if allow_tera and self._should_terastallize(active_request, move, mode) else None
        target_part = f" {target}" if target is not None else ""
        modifier_part = f" {modifier}" if modifier else ""
        choice = f"move {move_slot}{target_part}{modifier_part}"
        return choice, {
            "active_index": active_index,
            "choice": choice,
            "move_slot": move_slot,
            "move": move.get("id") or move.get("move") or f"move {move_slot}",
            "pokemon": pokemon_name,
            "target": target,
            "modifier": modifier,
            "score": round(score, 2),
            "reason": reason,
            "knowledge_used": "knowledge context" in reason,
            "learning_used": "learning profile" in reason,
            "legal_candidates": [
                {
                    "slot": slot,
                    "move": candidate.get("id") or candidate.get("move") or f"move {slot}",
                    "score": round(candidate_score, 2),
                    "knowledge_used": "knowledge context" in candidate_reason,
                    "learning_used": "learning profile" in candidate_reason,
                }
                for slot, candidate, candidate_score, candidate_reason in sorted(
                    scored_moves,
                    key=lambda item: item[2],
                    reverse=True,
                )
            ],
        }

    def _score_move(
        self,
        move: dict[str, Any],
        mode: str,
        pokemon_name: str = "",
        knowledge_context: dict[str, Any] | None = None,
        learning_profile: dict[str, Any] | None = None,
    ) -> tuple[float, str]:
        move_id = self.connector.to_id(move.get("id") or move.get("move"))
        knowledge_bonus, knowledge_reason = self._knowledge_move_bonus(move_id, pokemon_name, knowledge_context)
        learning_bonus, learning_reason = self._learning_move_bonus(move_id, learning_profile)
        if move_id in {"protect", "detect", "spikyshield", "kingsshield"}:
            score = 35.0 if mode == "defensive" else 15.0
            return self._with_policy_bonuses(
                score,
                f"protective move scored for {mode} mode",
                knowledge_bonus,
                knowledge_reason,
                learning_bonus,
                learning_reason,
            )
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
            "partingshot": 66.0,
            "snarl": 58.0,
            "reflect": 56.0,
            "lightscreen": 56.0,
        }
        if move_id in utility_scores:
            score = utility_scores[move_id]
            if mode == "defensive":
                score += 6
            if mode == "aggressive" and move_id not in {"fakeout", "spore"}:
                score -= 6
            return self._with_policy_bonuses(
                score,
                f"utility move {move_id} matched tactical priority",
                knowledge_bonus,
                knowledge_reason,
                learning_bonus,
                learning_reason,
            )
        score = float(move.get("basePower") or move.get("power") or 60)
        if move.get("target") in {"allAdjacentFoes", "allAdjacent", "foeSide"}:
            score += 15
        if move_id in {"explosion", "selfdestruct", "mistyexplosion", "finalgambit"}:
            score -= 260
        if move.get("pp") is not None:
            score += min(float(move.get("pp") or 0), 8.0) * 0.25
        if mode == "aggressive":
            score += 10
        return self._with_policy_bonuses(
            score,
            f"damage move scored from base power in {mode} mode",
            knowledge_bonus,
            knowledge_reason,
            learning_bonus,
            learning_reason,
        )

    def _with_policy_bonuses(
        self,
        score: float,
        reason: str,
        knowledge_bonus: float,
        knowledge_reason: str,
        learning_bonus: float,
        learning_reason: str,
    ) -> tuple[float, str]:
        score, reason = self._with_knowledge_bonus(score, reason, knowledge_bonus, knowledge_reason)
        return self._with_learning_bonus(score, reason, learning_bonus, learning_reason)

    def _with_knowledge_bonus(
        self,
        score: float,
        reason: str,
        knowledge_bonus: float,
        knowledge_reason: str,
    ) -> tuple[float, str]:
        if not knowledge_bonus:
            return score, reason
        return score + knowledge_bonus, f"{reason}; {knowledge_reason}"

    def _with_learning_bonus(
        self,
        score: float,
        reason: str,
        learning_bonus: float,
        learning_reason: str,
    ) -> tuple[float, str]:
        if not learning_bonus:
            return score, reason
        return score + learning_bonus, f"{reason}; {learning_reason}"

    def _learning_move_bonus(
        self,
        move_id: str,
        learning_profile: dict[str, Any] | None,
    ) -> tuple[float, str]:
        if not move_id or not self._needs_safer_play(learning_profile):
            return 0.0, ""
        if move_id in {"protect", "detect", "spikyshield", "kingsshield"}:
            return 90.0, "learning profile favors safer play after weak results"
        if move_id in {"partingshot", "snarl", "willowisp", "thunderwave", "reflect", "lightscreen"}:
            return 18.0, "learning profile favors defensive utility after weak results"
        return 0.0, ""

    def _needs_safer_play(self, learning_profile: dict[str, Any] | None) -> bool:
        if not learning_profile or int(learning_profile.get("battles") or 0) <= 0:
            return False
        win_rate = float(learning_profile.get("win_rate") or 0.0)
        average_reward = float(learning_profile.get("average_reward") or 0.0)
        faints_for = int(learning_profile.get("faints_for") or 0)
        faints_against = int(learning_profile.get("faints_against") or 0)
        return win_rate < 0.5 or average_reward < 50 or faints_against > faints_for

    def _knowledge_move_bonus(
        self,
        move_id: str,
        pokemon_name: str,
        knowledge_context: dict[str, Any] | None,
    ) -> tuple[float, str]:
        if not move_id or not knowledge_context:
            return 0.0, ""
        member = self._knowledge_member_for_pokemon(pokemon_name, knowledge_context)
        if member is None:
            return 0.0, ""
        text_parts = [
            str(member.get("species") or ""),
            str(member.get("query_key") or ""),
        ]
        for result in member.get("results") or []:
            if isinstance(result, dict):
                text_parts.extend(
                    str(result.get(key) or "")
                    for key in ("title", "snippet", "content", "description", "url")
                )
            else:
                text_parts.append(str(result))
        searchable_text = self.connector.to_id(" ".join(text_parts))
        if move_id in searchable_text:
            return 12.0, "knowledge context mentions this move"
        return 0.0, ""

    def _knowledge_member_for_pokemon(
        self,
        pokemon_name: str,
        knowledge_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        pokemon_id = self.connector.to_id(pokemon_name)
        if not pokemon_id:
            return None
        for member in knowledge_context.get("members") or []:
            if not isinstance(member, dict):
                continue
            member_id = self.connector.to_id(member.get("species") or member.get("query_key"))
            if member_id and (member_id == pokemon_id or member_id in pokemon_id or pokemon_id in member_id):
                return member
        return None

    def _target_for_move(self, move: dict[str, Any], active_pokemon: int | None = None) -> int | None:
        target_type = move.get("target")
        if target_type in {"normal", "any", "adjacentFoe"}:
            if active_pokemon == 1:
                return None
            return -1
        if target_type in {"adjacentAlly", "allyTeam"}:
            if active_pokemon == 1:
                return None
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

    def _active_species(self, request: ShowdownBattleRequest) -> list[str]:
        pokemon = request.side.get("pokemon") or []
        active = [self._display_pokemon(member) for member in pokemon if member.get("active")]
        if active:
            return active
        return [self._display_pokemon(member) for member in pokemon[:len(request.active)]]

    def _display_pokemon(self, member: dict[str, Any]) -> str:
        ident = str(member.get("ident") or member.get("details") or member.get("name") or "Unknown")
        return ident.split(": ", 1)[-1].split(",", 1)[0]


pokemon_showdown_battle_agent = PokemonShowdownBattleAgent()
