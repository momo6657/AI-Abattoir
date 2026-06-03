"""Stateful Pokemon Showdown session orchestration.

This service keeps live-session concerns separate from protocol parsing. It can
be exercised without a real websocket, and the same command stream can later be
sent through a connected Showdown socket.
"""

from __future__ import annotations

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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rooms: list[str] = field(default_factory=list)
    search: dict[str, Any] | None = None
    challenges: dict[str, Any] | None = None
    knowledge_context: dict[str, Any] = field(default_factory=dict)
    team_source: str = "none"
    team_reason: str = ""
    team_species: list[str] = field(default_factory=list)
    command_log: list[str] = field(default_factory=list)
    sent_log: list[str] = field(default_factory=list)
    event_log: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    last_error: str | None = None
    team: list[dict[str, Any]] | str | None = None
    login_assertion: str | None = None
    login_password: str | None = None
    auto_login: bool = True
    auto_accept_challenges: bool = False
    auto_research_team: bool = False
    accepted_challenges: list[str] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

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
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "rooms": self.rooms,
            "search": self.search,
            "challenges": self.challenges,
            "challenge_count": len((self.challenges or {}).get("challengesFrom") or {}),
            "challenge_usernames": list(((self.challenges or {}).get("challengesFrom") or {}).keys()),
            "knowledge_context": self.knowledge_context,
            "has_knowledge_context": bool(self.knowledge_context),
            "team_source": self.team_source,
            "team_reason": self.team_reason,
            "team_species": self.team_species,
            "has_team": self.team is not None,
            "auto_login": self.auto_login,
            "auto_accept_challenges": self.auto_accept_challenges,
            "auto_research_team": self.auto_research_team,
            "accepted_challenges": self.accepted_challenges,
            "has_login_assertion": self.login_assertion is not None,
            "has_login_password": self.login_password is not None,
            "pending_command_count": max(0, len(self.command_log) - len(self.sent_log)),
            "command_count": len(self.command_log),
            "sent_count": len(self.sent_log),
            "event_count": len(self.event_log),
            "decision_count": len(self.decisions),
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
        )
        self._ensure_team(state)
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
            plan = agent.plan(
                battle_request,
                mode=state.mode,
                team_size=team_size or state.team_size,
                active_pokemon=state.active_pokemon,
                allow_tera=allow_tera,
                knowledge_context=state.knowledge_context or None,
            )
            if plan.command:
                commands.append(plan.command)
                state.status = "responded"
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
        await connector.connect()
        state.status = "connected"
        sent = []
        if send_pending:
            sent = await self.flush_pending_commands(session_id)
        state.touch()
        return {"session": state.to_dict(), "sent": sent}

    async def flush_pending_commands(self, session_id: str) -> list[str]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        pending = state.command_log[len(state.sent_log):]
        for command in pending:
            await connector.send(command)
            state.sent_log.append(command)
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
        payload = await connector.receive()
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
    ) -> dict[str, Any]:
        results = []
        for _ in range(max_messages):
            result = await self.run_once(session_id, auto_respond=auto_respond, send_commands=send_commands)
            results.append(result)
            state = self._require_session(session_id)
            if stop_on_finished and state.status == "finished":
                break
        return {"session": self._require_session(session_id).to_dict(), "steps": results}

    async def close_session(self, session_id: str) -> dict[str, Any]:
        state = self._require_session(session_id)
        connector = self.connectors[session_id]
        await connector.close()
        if state.status != "finished":
            state.status = "closed"
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
        try:
            state.login_assertion = await connector.request_assertion(
                state.username,
                challstr,
                password=state.login_password,
            )
        except Exception as exc:
            state.last_error = f"Pokemon Showdown assertion request failed: {exc}"
            state.status = "error"
            raise ShowdownConnectionError(state.last_error) from exc

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
        generated = pokemon_showdown_team_factory.generate(state.battle_format, mode=state.mode)
        if not generated:
            return
        state.team = generated.team
        state.team_source = generated.source
        state.team_reason = generated.reason
        state.team_species = generated.species()

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

    def _apply_event_state(self, state: ShowdownSessionState, event: ShowdownEvent) -> None:
        if event.room_id and event.room_id not in state.rooms:
            state.rooms.append(event.room_id)
        if event.event_type == "init" and event.args and event.args[0] == "battle":
            state.status = "battling"
        elif event.event_type == "request":
            state.status = "choosing"
        elif event.event_type == "win":
            state.status = "finished"
            state.result = {"type": "win", "winner": event.args[0] if event.args else None}
        elif event.event_type == "tie":
            state.status = "finished"
            state.result = {"type": "tie"}
        elif event.event_type == "error":
            state.last_error = "|".join(event.args)

    def _update_analysis(self, state: ShowdownSessionState) -> None:
        state.analysis = pokemon_showdown_analysis_service.summarize(
            state.event_log,
            state.decisions,
            username=state.username,
        )

    def _record_learning_if_finished(self, state: ShowdownSessionState) -> dict[str, Any]:
        return self.learning_service.record_session(
            session_id=state.session_id,
            username=state.username,
            battle_format=state.battle_format,
            showdown_format=state.showdown_format,
            mode=state.mode,
            analysis=state.analysis,
            decisions=state.decisions,
        )

    def _serialize_event(self, event: ShowdownEvent) -> dict[str, Any]:
        return {
            "room_id": event.room_id,
            "event_type": event.event_type,
            "args": event.args,
            "raw": event.raw,
        }


pokemon_showdown_session_service = PokemonShowdownSessionService()
