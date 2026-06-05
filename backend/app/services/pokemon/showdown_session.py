"""Stateful Pokemon Showdown session orchestration.

This service keeps live-session concerns separate from protocol parsing. It can
be exercised without a real websocket, and the same command stream can later be
sent through a connected Showdown socket.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.pokemon.format_catalog import pokemon_format_catalog
from app.services.pokemon.showdown_battle_agent import (
    PokemonShowdownBattleAgent,
    ShowdownChoicePlan,
)
from app.services.pokemon.showdown_analysis import pokemon_showdown_analysis_service
from app.services.pokemon.showdown_connector import (
    PokemonShowdownConnector,
    ShowdownConnectionError,
    ShowdownEvent,
)
from app.services.pokemon.showdown_learning import PokemonShowdownLearningService
from app.services.pokemon.showdown_team_factory import pokemon_showdown_team_factory


@dataclass
class ShowdownSessionState:
    session_id: str
    username: str
    battle_format: str = "gen9vgc2024regg"
    showdown_format: str = "gen9vgc2024regg"
    battle_type: str = "double"
    team_size: int = 4
    active_pokemon: int = 2
    requires_team: bool = True
    mode: str = "balanced"
    requested_mode: str = "balanced"
    mode_source: str = "manual"
    mode_recommendation: dict[str, Any] = field(default_factory=dict)
    status: str = "ready"
    connection_diagnostics: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rooms: list[str] = field(default_factory=list)
    room_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    search: dict[str, Any] | None = None
    challenges: dict[str, Any] | None = None
    knowledge_context: dict[str, Any] = field(default_factory=dict)
    team_source: str = "none"
    team_reason: str = ""
    team_species: list[str] = field(default_factory=list)
    team_adjustments: list[dict[str, str]] = field(default_factory=list)
    command_log: list[str] = field(default_factory=list)
    sent_log: list[str] = field(default_factory=list)
    event_log: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    handled_requests: dict[str, str | None] = field(default_factory=dict)
    duplicate_request_count: int = 0
    analysis: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    run_history: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None
    team: list[dict[str, Any]] | str | None = None
    login_assertion: str | None = None
    login_password: str | None = None
    auto_login: bool = True
    auto_accept_challenges: bool = False
    auto_research_team: bool = False
    accepted_challenges: list[str] = field(default_factory=list)
    learning_profile: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def _team_preview(self) -> list[dict[str, Any]]:
        if not isinstance(self.team, list):
            return []

        preview: list[dict[str, Any]] = []
        for index, member in enumerate(self.team):
            moves = member.get("moves") or []
            preview.append(
                {
                    "slot": index + 1,
                    "species": str(member.get("species") or member.get("name") or f"Slot {index + 1}"),
                    "name": member.get("name"),
                    "item": member.get("item"),
                    "ability": member.get("ability"),
                    "tera_type": member.get("tera_type"),
                    "moves": [str(move.get("name") if isinstance(move, dict) else move) for move in moves],
                }
            )
        return preview

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "username": self.username,
            "battle_format": self.battle_format,
            "showdown_format": self.showdown_format,
            "battle_type": self.battle_type,
            "team_size": self.team_size,
            "active_pokemon": self.active_pokemon,
            "requires_team": self.requires_team,
            "mode": self.mode,
            "requested_mode": self.requested_mode,
            "mode_source": self.mode_source,
            "mode_recommendation": self.mode_recommendation,
            "status": self.status,
            "connection_diagnostics": dict(self.connection_diagnostics),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "rooms": self.rooms,
            "room_details": self.room_details,
            "search": self.search,
            "challenges": self.challenges,
            "challenge_count": len((self.challenges or {}).get("challengesFrom") or {}),
            "challenge_usernames": list(((self.challenges or {}).get("challengesFrom") or {}).keys()),
            "knowledge_context": self.knowledge_context,
            "has_knowledge_context": bool(self.knowledge_context),
            "team_source": self.team_source,
            "team_reason": self.team_reason,
            "team_species": self.team_species,
            "team_adjustments": self.team_adjustments,
            "team_preview": self._team_preview(),
            "has_team": self.team is not None,
            "auto_login": self.auto_login,
            "auto_accept_challenges": self.auto_accept_challenges,
            "auto_research_team": self.auto_research_team,
            "accepted_challenges": self.accepted_challenges,
            "learning_profile": self.learning_profile,
            "has_login_assertion": self.login_assertion is not None,
            "has_login_password": self.login_password is not None,
            "pending_command_count": max(0, len(self.command_log) - len(self.sent_log)),
            "command_count": len(self.command_log),
            "sent_count": len(self.sent_log),
            "event_count": len(self.event_log),
            "decision_count": len(self.decisions),
            "handled_request_count": len(self.handled_requests),
            "duplicate_request_count": self.duplicate_request_count,
            "room_count": len(self.rooms),
            "last_command": self.command_log[-1] if self.command_log else None,
            "last_sent": self.sent_log[-1] if self.sent_log else None,
            "last_event": self.event_log[-1] if self.event_log else None,
            "command_log": self.command_log,
            "sent_log": self.sent_log,
            "event_log": self.event_log,
            "decisions": self.decisions,
            "analysis": self.analysis,
            "result": self.result,
            "last_run_summary": dict(self.run_history[-1]) if self.run_history else None,
            "run_history": [dict(item) for item in self.run_history],
            "run_history_count": len(self.run_history),
            "last_error": self.last_error,
        }


class PokemonShowdownSessionService:
    """In-memory orchestration layer for autonomous Showdown sessions."""

    def __init__(self, learning_service: PokemonShowdownLearningService | None = None):
        self.sessions: dict[str, ShowdownSessionState] = {}
        self.connectors: dict[str, PokemonShowdownConnector] = {}
        self.agents: dict[str, PokemonShowdownBattleAgent] = {}
        self.learning_service = learning_service or PokemonShowdownLearningService()

    def create_session(
        self,
        *,
        username: str,
        team: list[dict[str, Any]] | str | None,
        battle_format: str = "gen9vgc2024regg",
        mode: str = "balanced",
        requested_mode: str | None = None,
        mode_source: str = "manual",
        mode_recommendation: dict[str, Any] | None = None,
        login_assertion: str | None = None,
        login_password: str | None = None,
        auto_login: bool = True,
        auto_accept_challenges: bool = False,
        auto_research_team: bool = False,
        auto_search: bool = False,
        learning_profile: dict[str, Any] | None = None,
        connector: PokemonShowdownConnector | None = None,
    ) -> ShowdownSessionState:
        session_id = uuid4().hex
        connector = connector or PokemonShowdownConnector()
        format_info = pokemon_format_catalog.get(battle_format)
        team_source, team_reason, team_species = self._prepare_team(team, format_info.id, mode)
        agent = PokemonShowdownBattleAgent(connector)
        state = ShowdownSessionState(
            session_id=session_id,
            username=username,
            battle_format=format_info.id,
            showdown_format=format_info.showdown_format,
            battle_type=format_info.battle_type,
            team_size=format_info.team_size,
            active_pokemon=format_info.active_pokemon,
            requires_team=format_info.requires_team,
            mode=mode,
            requested_mode=requested_mode or mode,
            mode_source=mode_source,
            mode_recommendation=mode_recommendation or {},
            status="searching" if auto_search else "ready",
            team=team,
            team_source=team_source,
            team_reason=team_reason,
            team_species=team_species,
            login_assertion=login_assertion,
            login_password=login_password,
            auto_login=auto_login,
            auto_accept_challenges=auto_accept_challenges,
            auto_research_team=auto_research_team,
            learning_profile=learning_profile or {},
        )
        self._ensure_team(state)
        self._set_diagnostic(
            state,
            "ready",
            connected=False,
            websocket_url=connector.server_url,
            login_url=connector.login_url,
        )
        if auto_search:
            state.command_log.extend(connector.build_ladder_search_messages(state.team, format_info.showdown_format))
        self.sessions[session_id] = state
        self.connectors[session_id] = connector
        self.agents[session_id] = agent
        return state

    def get_session(self, session_id: str) -> ShowdownSessionState | None:
        return self.sessions.get(session_id)

    def list_sessions(self) -> list[ShowdownSessionState]:
        return sorted(self.sessions.values(), key=lambda item: item.created_at, reverse=True)

    def delete_session(self, session_id: str) -> bool:
        existed = session_id in self.sessions
        self.sessions.pop(session_id, None)
        self.connectors.pop(session_id, None)
        self.agents.pop(session_id, None)
        return existed

    def process_payload(
        self,
        session_id: str,
        payload: str,
        *,
        auto_respond: bool = True,
        team_size: int | None = None,
        allow_tera: bool = True,
    ) -> dict[str, Any]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        agent = self.agents[session_id]
        events = connector.parse_message(payload)
        state.event_log.extend(self._serialize_event(event) for event in events)
        commands: list[str] = []
        plan: ShowdownChoicePlan | None = None

        for event in events:
            self._apply_event_state(state, event)

        challstr = connector.extract_challstr(events)
        if challstr and state.login_assertion:
            commands.append(connector.build_login_message(state.username, state.login_assertion))
            state.status = "authenticated"

        battle_request = connector.parse_battle_request(events)
        if auto_respond and battle_request and battle_request.needs_choice:
            request_key = self._request_key(battle_request.room_id, battle_request.request_id)
            if request_key and request_key in state.handled_requests:
                state.duplicate_request_count += 1
                plan = ShowdownChoicePlan(
                    room_id=battle_request.room_id,
                    command=None,
                    choices=[],
                    request_id=battle_request.request_id,
                    decision_type="duplicate_request",
                    reason=f"Request {request_key} was already answered; no duplicate command was queued.",
                    needs_choice=False,
                )
                state.status = "responded"
            else:
                plan = agent.plan(
                    battle_request,
                    mode=state.mode,
                    team_size=team_size or state.team_size,
                    active_pokemon=state.active_pokemon,
                    allow_tera=allow_tera,
                    knowledge_context=state.knowledge_context or None,
                    learning_profile=state.learning_profile or None,
                    team_context=state.team if isinstance(state.team, list) else None,
                    battlefield_context=self._battlefield_context(state, battle_request.room_id),
                )
                if plan.command:
                    commands.append(plan.command)
                    state.status = "responded"
                if request_key and plan.command:
                    state.handled_requests[request_key] = plan.command
                state.decisions.append(plan.to_dict())

        search = connector.parse_search_update(events)
        if search is not None:
            state.search = search
            if state.status != "finished" and search.get("searching"):
                state.status = "searching"

        challenges = connector.parse_challenge_update(events)
        if challenges is not None:
            state.challenges = challenges
            if state.auto_accept_challenges:
                commands.extend(self._auto_accept_challenge_commands(state, challenges))

        if commands:
            state.command_log.extend(commands)
        self._update_analysis(state)
        learning_profile = self._record_learning_if_finished(state)
        state.touch()
        return {
            "session": state.to_dict(),
            "events": [self._serialize_event(event) for event in events],
            "commands": commands,
            "decision": None if plan is None else plan.to_dict(),
            "learning_profile": learning_profile,
        }

    async def connect_session(self, session_id: str, *, send_pending: bool = True) -> dict[str, Any]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        self._set_diagnostic(state, "connecting", connected=False, websocket_url=connector.server_url)
        try:
            await connector.connect()
        except Exception as exc:
            self._record_diagnostic_error(state, "connect_error", exc)
            raise ShowdownConnectionError(state.last_error or str(exc)) from exc
        state.status = "connected"
        self._set_diagnostic(state, "connected", connected=True)
        sent = []
        if send_pending:
            sent = await self.flush_pending_commands(session_id)
        state.touch()
        return {"session": state.to_dict(), "sent": sent}

    async def flush_pending_commands(self, session_id: str) -> list[str]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        pending = state.command_log[len(state.sent_log):]
        self._set_diagnostic(state, "sending" if pending else "send_idle", pending_count=len(pending))
        for command in pending:
            try:
                await connector.send(command)
            except Exception as exc:
                self._record_diagnostic_error(state, "send_error", exc)
                raise ShowdownConnectionError(state.last_error or str(exc)) from exc
            state.sent_log.append(command)
        self._set_diagnostic(
            state,
            "sent" if pending else "send_idle",
            pending_count=max(0, len(state.command_log) - len(state.sent_log)),
            sent_count=len(state.sent_log),
        )
        state.touch()
        return pending

    async def run_once(
        self,
        session_id: str,
        *,
        auto_respond: bool = True,
        send_commands: bool = True,
        team_size: int | None = None,
        allow_tera: bool = True,
    ) -> dict[str, Any]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        self._set_diagnostic(state, "receiving")
        try:
            payload = await connector.receive()
        except Exception as exc:
            self._record_diagnostic_error(state, "receive_error", exc, prefix="Pokemon Showdown receive failed")
            raise ShowdownConnectionError(state.last_error) from exc
        self._set_diagnostic(state, "received", last_payload_size=len(payload))
        await self._prepare_login_assertion_from_payload(state, connector, payload)
        result = self.process_payload(
            session_id,
            payload,
            auto_respond=auto_respond,
            team_size=team_size,
            allow_tera=allow_tera,
        )
        sent = await self.flush_pending_commands(session_id) if send_commands else []
        result["sent"] = sent
        result["session"] = state.to_dict()
        return result

    async def run_until(
        self,
        session_id: str,
        *,
        max_messages: int = 50,
        stop_on_finished: bool = True,
        auto_respond: bool = True,
        send_commands: bool = True,
        team_size: int | None = None,
        allow_tera: bool = True,
        stop_on_error: bool = True,
    ) -> dict[str, Any]:
        results = []
        for _ in range(max_messages):
            try:
                result = await self.run_once(
                    session_id,
                    auto_respond=auto_respond,
                    send_commands=send_commands,
                    team_size=team_size,
                    allow_tera=allow_tera,
                )
            except ShowdownConnectionError as exc:
                state = self._require_session(session_id)
                state.last_error = str(exc)
                state.status = "error"
                state.touch()
                if not stop_on_error:
                    raise
                results.append({
                    "session": state.to_dict(),
                    "commands": [],
                    "sent": [],
                    "error": str(exc),
                })
                break
            results.append(result)
            state = self._require_session(session_id)
            if stop_on_finished and state.status == "finished":
                break
        state = self._require_session(session_id)
        run_summary = self._store_run_summary(
            state,
            self._build_run_summary(state, results, max_messages=max_messages),
        )
        return {
            "session": state.to_dict(),
            "steps": results,
            "run_summary": run_summary,
        }

    async def autopilot(
        self,
        session_id: str,
        *,
        max_messages: int = 50,
        stop_on_finished: bool = True,
        auto_respond: bool = True,
        send_commands: bool = True,
        team_size: int | None = None,
        allow_tera: bool = True,
        auto_search: bool = True,
        close_on_finish: bool = False,
        stop_on_error: bool = True,
    ) -> dict[str, Any]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        actions: list[str] = []
        initial_sent: list[str] = []

        if not connector.websocket:
            self._set_diagnostic(state, "connecting", connected=False, websocket_url=connector.server_url)
            try:
                await connector.connect()
            except Exception as exc:
                self._record_diagnostic_error(state, "connect_error", exc)
                raise ShowdownConnectionError(state.last_error or str(exc)) from exc
            state.status = "connected"
            self._set_diagnostic(state, "connected", connected=True)
            actions.append("connected")

        if auto_search and self._should_queue_ladder_search(state):
            self.start_ladder_search(session_id)
            actions.append("search_queued")
            if send_commands:
                initial_sent.extend(await self.flush_pending_commands(session_id))
        elif send_commands:
            pending = await self.flush_pending_commands(session_id)
            if pending:
                actions.append("pending_flushed")
                initial_sent.extend(pending)

        run_result = await self.run_until(
            session_id,
            max_messages=max_messages,
            stop_on_finished=stop_on_finished,
            auto_respond=auto_respond,
            send_commands=send_commands,
            team_size=team_size,
            allow_tera=allow_tera,
            stop_on_error=stop_on_error,
        )
        if close_on_finish and self._require_session(session_id).status == "finished":
            await self.close_session(session_id)
            actions.append("closed")
        run_summary = dict(run_result.get("run_summary") or {})
        run_summary["actions"] = actions
        run_summary["initial_sent_count"] = len(initial_sent)
        run_summary["total_sent_count"] = int(run_summary.get("sent_count") or 0) + len(initial_sent)
        state = self._require_session(session_id)
        run_summary = self._store_run_summary(state, run_summary, replace_last=True)
        session = state.to_dict()
        return {
            "session": session,
            "steps": run_result["steps"],
            "sent": initial_sent,
            "actions": actions,
            "run_summary": run_summary,
        }

    async def close_session(self, session_id: str) -> dict[str, Any]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        await connector.close()
        if state.status != "finished":
            state.status = "closed"
        self._set_diagnostic(state, "closed", connected=False)
        state.touch()
        return state.to_dict()

    def start_ladder_search(self, session_id: str) -> list[str]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        self._ensure_team(state)
        commands = connector.build_ladder_search_messages(state.team, state.showdown_format)
        state.command_log.extend(commands)
        state.status = "searching"
        state.touch()
        return commands

    def _should_queue_ladder_search(self, state: ShowdownSessionState) -> bool:
        if state.status in {"searching", "battling", "choosing", "responded", "finished"}:
            return False
        if (state.search or {}).get("searching"):
            return False
        search_command = f"|/search {state.showdown_format}"
        return search_command not in state.command_log

    def _build_run_summary(
        self,
        state: ShowdownSessionState,
        steps: list[dict[str, Any]],
        *,
        max_messages: int,
    ) -> dict[str, Any]:
        command_count = sum(len(step.get("commands") or []) for step in steps)
        sent_count = sum(len(step.get("sent") or []) for step in steps)
        error_step = next((step for step in steps if step.get("error")), None)
        decisions = [step.get("decision") for step in steps if step.get("decision")]
        last_decision = decisions[-1] if decisions else None
        if error_step:
            stopped_reason = "error"
        elif state.status == "finished":
            stopped_reason = "finished"
        elif len(steps) >= max_messages:
            stopped_reason = "max_messages"
        else:
            stopped_reason = state.status or "idle"
        return {
            "status": state.status,
            "stopped_reason": stopped_reason,
            "step_count": len(steps),
            "max_messages": max_messages,
            "command_count": command_count,
            "sent_count": sent_count,
            "total_sent_count": sent_count,
            "decision_count": len(decisions),
            "last_decision_type": last_decision.get("decision_type") if isinstance(last_decision, dict) else None,
            "last_command": last_decision.get("command") if isinstance(last_decision, dict) else None,
            "error": error_step.get("error") if isinstance(error_step, dict) else state.last_error,
            "result": state.result,
        }

    def _store_run_summary(
        self,
        state: ShowdownSessionState,
        summary: dict[str, Any],
        *,
        replace_last: bool = False,
    ) -> dict[str, Any]:
        stored = dict(summary)
        if replace_last and state.run_history:
            stored["run_number"] = state.run_history[-1].get("run_number") or len(state.run_history)
            state.run_history[-1] = stored
        else:
            previous_number = int(state.run_history[-1].get("run_number") or len(state.run_history)) if state.run_history else 0
            stored["run_number"] = previous_number + 1
            state.run_history.append(stored)
            if len(state.run_history) > 10:
                state.run_history = state.run_history[-10:]
        state.touch()
        return stored

    def _set_diagnostic(self, state: ShowdownSessionState, stage: str, **updates: Any) -> None:
        next_diagnostics = dict(state.connection_diagnostics)
        next_diagnostics.update(updates)
        next_diagnostics["stage"] = stage
        next_diagnostics["updated_at"] = datetime.now(timezone.utc).isoformat()
        state.connection_diagnostics = next_diagnostics

    def _record_diagnostic_error(
        self,
        state: ShowdownSessionState,
        stage: str,
        exc: Exception,
        *,
        prefix: str | None = None,
    ) -> None:
        message = f"{prefix}: {exc}" if prefix else f"Pokemon Showdown {stage.replace('_', ' ')}: {exc}"
        state.last_error = message
        state.status = "error"
        self._set_diagnostic(
            state,
            stage,
            connected=False,
            last_error=message,
        )
        state.touch()

    def cancel_ladder_search(self, session_id: str) -> list[str]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        commands = [connector.build_cancel_search_message()]
        state.command_log.extend(commands)
        if state.status == "searching":
            state.status = "ready"
        state.touch()
        return commands

    def accept_challenge(self, session_id: str, username: str | None = None) -> list[str]:
        state = self._require_session(session_id)
        challenger = self._resolve_challenge_username(state, username)
        commands = self._build_accept_challenge_commands(state, challenger)
        state.command_log.extend(commands)
        state.status = "challenge_accepted"
        state.touch()
        return commands

    def reject_challenge(self, session_id: str, username: str | None = None) -> list[str]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        challenger = self._resolve_challenge_username(state, username)
        commands = [connector.build_reject_challenge_message(challenger)]
        state.command_log.extend(commands)
        state.status = "challenge_rejected"
        state.touch()
        return commands

    def _resolve_challenge_username(self, state: ShowdownSessionState, username: str | None) -> str:
        if username:
            return username
        challenges_from = (state.challenges or {}).get("challengesFrom") or {}
        for challenger in challenges_from.keys():
            if challenger:
                return str(challenger)
        raise ValueError("No incoming Pokemon Showdown challenge is available.")

    def _auto_accept_challenge_commands(self, state: ShowdownSessionState, challenges: dict[str, Any]) -> list[str]:
        challenges_from = challenges.get("challengesFrom") or {}
        for challenger, challenge_format in challenges_from.items():
            challenger_name = str(challenger or "")
            if not challenger_name or challenger_name in state.accepted_challenges:
                continue
            if not self._challenge_format_matches(state, challenge_format):
                continue
            commands = self._build_accept_challenge_commands(state, challenger_name)
            state.status = "challenge_accepted"
            return commands
        return []

    def _build_accept_challenge_commands(self, state: ShowdownSessionState, challenger: str) -> list[str]:
        connector = self.connectors[state.session_id]
        self._ensure_team(state)
        commands = connector.build_accept_challenge_messages(challenger, state.team)
        if challenger not in state.accepted_challenges:
            state.accepted_challenges.append(challenger)
        return commands

    def _challenge_format_matches(self, state: ShowdownSessionState, challenge_format: Any) -> bool:
        if not challenge_format:
            return False
        try:
            return pokemon_format_catalog.get(str(challenge_format)).showdown_format == state.showdown_format
        except ValueError:
            return str(challenge_format).lower() == state.showdown_format.lower()

    async def _prepare_login_assertion_from_payload(
        self,
        state: ShowdownSessionState,
        connector: PokemonShowdownConnector,
        payload: str,
    ) -> None:
        if not state.auto_login or state.login_assertion:
            return
        challstr = self._extract_challstr_from_payload(payload)
        if not challstr:
            return
        self._set_diagnostic(state, "requesting_assertion", has_login_password=state.login_password is not None)
        try:
            state.login_assertion = await connector.request_assertion(
                state.username,
                challstr,
                password=state.login_password,
            )
        except Exception as exc:
            self._record_diagnostic_error(
                state,
                "assertion_error",
                exc,
                prefix="Pokemon Showdown assertion request failed",
            )
            raise ShowdownConnectionError(state.last_error) from exc
        self._set_diagnostic(state, "assertion_ready", has_login_assertion=True)

    def _extract_challstr_from_payload(self, payload: str) -> str | None:
        for raw_line in payload.splitlines():
            if not raw_line.startswith("|challstr|"):
                continue
            parts = raw_line.split("|")
            return "|".join(parts[2:]) if len(parts) > 2 else None
        return None

    def _ensure_team(self, state: ShowdownSessionState) -> None:
        if state.team is not None or not state.requires_team:
            return
        generated = pokemon_showdown_team_factory.generate(
            state.battle_format,
            mode=state.mode,
            learning_profile=state.learning_profile,
        )
        if not generated:
            return
        state.team = generated.team
        state.team_source = generated.source
        state.team_reason = generated.reason
        state.team_species = generated.species()
        state.team_adjustments = generated.adjustments

    def _prepare_team(
        self,
        team: list[dict[str, Any]] | str | None,
        battle_format: str,
        mode: str,
    ) -> tuple[str, str, list[str]]:
        format_info = pokemon_format_catalog.get(battle_format)
        if isinstance(team, list):
            return (
                "provided",
                "Using the team provided in the session request.",
                [str(member.get("species") or member.get("name") or "Unknown") for member in team],
            )
        if isinstance(team, str) and team:
            return "packed", "Using the packed Showdown team provided in the session request.", []
        if not format_info.requires_team:
            return "not_required", f"{format_info.name} supplies teams on Pokemon Showdown.", []
        return "auto", f"No team was provided; an autonomous {mode} team will be generated.", []

    def analyze_session(self, session_id: str) -> dict[str, Any]:
        state = self._require_session(session_id)
        self._update_analysis(state)
        self._record_learning_if_finished(state)
        state.touch()
        return state.analysis

    def learning_profile(self, username: str, battle_format: str) -> dict[str, Any]:
        format_info = pokemon_format_catalog.get(battle_format)
        return self.learning_service.profile(
            username=username,
            battle_format=format_info.id,
        )

    def list_learning_profiles(self) -> list[dict[str, Any]]:
        return self.learning_service.list_profiles()

    def attach_knowledge_context(self, session_id: str, context: dict[str, Any]) -> ShowdownSessionState:
        state = self._require_session(session_id)
        state.knowledge_context = context
        state.touch()
        return state

    def _require_session(self, session_id: str) -> ShowdownSessionState:
        state = self.sessions.get(session_id)
        if state is None:
            raise KeyError(f"Pokemon Showdown session not found: {session_id}")
        return state

    def _request_key(self, room_id: str, request_id: int | None) -> str | None:
        if not room_id or request_id is None:
            return None
        return f"{room_id}:{request_id}"

    def _apply_event_state(self, state: ShowdownSessionState, event: ShowdownEvent) -> None:
        room = self._sync_room_event(state, event)
        if event.event_type == "init" and event.args and event.args[0] == "battle":
            state.status = "battling"
            if room is not None:
                room["status"] = "battling"
        elif event.event_type == "request":
            state.status = "choosing"
            if room is not None:
                room["status"] = "choosing"
        elif event.event_type == "win":
            state.status = "finished"
            state.result = {"type": "win", "winner": event.args[0] if event.args else None}
            if room is not None:
                room["status"] = "finished"
                room["result"] = state.result
        elif event.event_type == "tie":
            state.status = "finished"
            state.result = {"type": "tie"}
            if room is not None:
                room["status"] = "finished"
                room["result"] = state.result
        elif event.event_type == "error":
            state.last_error = "|".join(event.args)
            if room is not None:
                room["last_error"] = state.last_error
        if room is not None:
            self._sync_battlefield_event(room, event)

    def _sync_room_event(self, state: ShowdownSessionState, event: ShowdownEvent) -> dict[str, Any] | None:
        if not event.room_id:
            return None
        if event.room_id not in state.rooms:
            state.rooms.append(event.room_id)

        room = state.room_details.setdefault(
            event.room_id,
            {
                "room_id": event.room_id,
                "status": "active",
                "players": {},
                "rules": [],
            },
        )
        room["last_event_type"] = event.event_type

        if event.event_type == "title" and event.args:
            room["title"] = event.args[0]
        elif event.event_type == "gametype" and event.args:
            room["game_type"] = event.args[0]
        elif event.event_type == "gen" and event.args:
            room["generation"] = self._to_int(event.args[0])
        elif event.event_type == "tier" and event.args:
            room["tier"] = event.args[0]
        elif event.event_type == "rated":
            room["rated"] = True
            room["rated_message"] = "|".join(event.args) if event.args else ""
        elif event.event_type == "rule" and event.args:
            rule = event.args[0]
            if rule not in room["rules"]:
                room["rules"].append(rule)
        elif event.event_type == "poke":
            self._sync_room_preview(room, event.args)
        elif event.event_type == "player":
            self._sync_room_player(state, room, event.args)
        elif event.event_type == "request" and event.args:
            try:
                payload = json.loads(event.args[0])
            except json.JSONDecodeError:
                payload = {}
            room["request_id"] = payload.get("rqid")
            room["waiting"] = bool(payload.get("wait"))
            room["team_preview"] = bool(payload.get("teamPreview"))
            self._sync_battlefield_request(room, payload)
        return room

    def _sync_battlefield_event(self, room: dict[str, Any], event: ShowdownEvent) -> None:
        if event.event_type in {"switch", "drag", "replace"} and event.args:
            ident = self._parse_ident(event.args[0])
            if not ident:
                return
            condition = event.args[2] if len(event.args) > 2 else ""
            self._update_battlefield_slot(room, ident, condition=condition, active=True, fainted=False)
        elif event.event_type in {"-damage", "-heal"} and len(event.args) >= 2:
            ident = self._parse_ident(event.args[0])
            if not ident:
                return
            condition = event.args[1]
            self._update_battlefield_slot(room, ident, condition=condition)
        elif event.event_type == "faint" and event.args:
            ident = self._parse_ident(event.args[0])
            if not ident:
                return
            self._update_battlefield_slot(room, ident, condition="0 fnt", active=False, fainted=True)

    def _sync_battlefield_request(self, room: dict[str, Any], payload: dict[str, Any]) -> None:
        for member in (payload.get("side") or {}).get("pokemon") or []:
            ident = self._parse_ident(member.get("ident") or "")
            if not ident:
                continue
            self._update_battlefield_slot(
                room,
                ident,
                condition=str(member.get("condition") or ""),
                active=bool(member.get("active")),
                fainted=self._condition_is_fainted(str(member.get("condition") or "")),
            )

    def _update_battlefield_slot(
        self,
        room: dict[str, Any],
        ident: dict[str, str],
        *,
        condition: str = "",
        active: bool | None = None,
        fainted: bool | None = None,
    ) -> None:
        battlefield = room.setdefault("battlefield", {"sides": {}})
        side = battlefield.setdefault("sides", {}).setdefault(ident["side"], {"active": {}})
        slot = side.setdefault("active", {}).setdefault(ident["position"], {})
        slot.update({
            "side": ident["side"],
            "position": ident["position"],
            "ident": ident["raw"],
            "pokemon": ident["pokemon"],
        })
        if condition:
            slot["condition"] = condition
            slot["hp_fraction"] = self._hp_fraction(condition)
            slot["fainted"] = self._condition_is_fainted(condition)
        if active is not None:
            slot["active"] = active
        if fainted is not None:
            slot["fainted"] = fainted

    def _battlefield_context(self, state: ShowdownSessionState, room_id: str) -> dict[str, Any]:
        room = state.room_details.get(room_id) or {}
        battlefield = room.get("battlefield") or {}
        sides = battlefield.get("sides") or {}
        agent_side = room.get("agent_side")
        opponent_side = room.get("opponent_side")
        if not opponent_side and agent_side:
            opponent_side = "p2" if agent_side == "p1" else "p1"
        opponents = self._battlefield_side_slots(sides.get(opponent_side or "") or {})
        allies = self._battlefield_side_slots(sides.get(agent_side or "") or {})
        preview = room.get("preview") or {}
        return {
            "room_id": room_id,
            "agent_side": agent_side,
            "opponent_side": opponent_side,
            "allies": allies,
            "opponents": opponents,
            "ally_preview": list(preview.get(agent_side or "") or []),
            "opponent_preview": list(preview.get(opponent_side or "") or []),
        }

    def _battlefield_side_slots(self, side: dict[str, Any]) -> list[dict[str, Any]]:
        slots = side.get("active") or {}
        return [
            slots[position]
            for position in sorted(slots.keys())
            if isinstance(slots.get(position), dict)
        ]

    def _parse_ident(self, value: Any) -> dict[str, str] | None:
        text = str(value or "")
        if not text:
            return None
        side_position, _, pokemon = text.partition(": ")
        if len(side_position) < 3:
            return None
        return {
            "raw": text,
            "side": side_position[:2],
            "position": side_position[2:],
            "pokemon": pokemon or text,
        }

    def _hp_fraction(self, condition: str) -> float | None:
        condition = str(condition or "").split(" ", 1)[0]
        if "/" not in condition:
            return 0.0 if condition == "0" else None
        current, _, maximum = condition.partition("/")
        try:
            max_value = float(maximum)
            if max_value <= 0:
                return None
            return max(0.0, min(1.0, float(current) / max_value))
        except ValueError:
            return None

    def _condition_is_fainted(self, condition: str) -> bool:
        condition = str(condition or "").lower()
        return " fnt" in condition or condition == "0 fnt" or condition.endswith("/0")

    def _sync_room_preview(self, room: dict[str, Any], args: list[str]) -> None:
        side = str(args[0]) if len(args) > 0 else ""
        details = str(args[1]) if len(args) > 1 else ""
        if not side or not details:
            return
        species = details.split(",", 1)[0].strip() or details
        item_hint = str(args[2]) if len(args) > 2 and args[2] else None
        entry = {
            "side": side,
            "species": species,
            "details": details,
            "item_hint": item_hint,
        }
        preview = room.setdefault("preview", {}).setdefault(side, [])
        if any(existing.get("details") == details for existing in preview if isinstance(existing, dict)):
            return
        preview.append(entry)

    def _sync_room_player(self, state: ShowdownSessionState, room: dict[str, Any], args: list[str]) -> None:
        side = str(args[0]) if len(args) > 0 else ""
        username = str(args[1]) if len(args) > 1 else ""
        if not side or not username:
            return

        player = {
            "side": side,
            "username": username,
            "avatar": str(args[2]) if len(args) > 2 and args[2] else None,
            "rating": str(args[3]) if len(args) > 3 and args[3] else None,
        }
        room.setdefault("players", {})[side] = player
        if self._normalize_username(username) == self._normalize_username(state.username):
            room["agent_side"] = side
            room["agent_username"] = username
        else:
            room["opponent_side"] = side
            room["opponent_username"] = username

    def _normalize_username(self, username: str | None) -> str:
        return "".join(ch for ch in str(username or "").lower() if ch.isalnum())

    def _to_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _update_analysis(self, state: ShowdownSessionState) -> None:
        state.analysis = pokemon_showdown_analysis_service.summarize(
            state.event_log,
            state.decisions,
            username=state.username,
        )

    def _record_learning_if_finished(self, state: ShowdownSessionState) -> dict[str, Any]:
        profile = self.learning_service.record_session(
            session_id=state.session_id,
            username=state.username,
            battle_format=state.battle_format,
            showdown_format=state.showdown_format,
            mode=state.mode,
            analysis=state.analysis,
            decisions=state.decisions,
        )
        if state.analysis.get("status") in {"win", "loss", "tie", "finished"}:
            state.learning_profile = profile
        return profile

    def _serialize_event(self, event: ShowdownEvent) -> dict[str, Any]:
        return {
            "room_id": event.room_id,
            "event_type": event.event_type,
            "args": event.args,
            "raw": event.raw,
        }


pokemon_showdown_session_service = PokemonShowdownSessionService()
