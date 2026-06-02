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
from app.services.pokemon.showdown_connector import (
    PokemonShowdownConnector,
    ShowdownEvent,
)


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
    status: str = "ready"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rooms: list[str] = field(default_factory=list)
    search: dict[str, Any] | None = None
    challenges: dict[str, Any] | None = None
    command_log: list[str] = field(default_factory=list)
    sent_log: list[str] = field(default_factory=list)
    event_log: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    last_error: str | None = None
    team: list[dict[str, Any]] | str | None = None
    login_assertion: str | None = None

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
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "rooms": self.rooms,
            "search": self.search,
            "challenges": self.challenges,
            "command_log": self.command_log,
            "sent_log": self.sent_log,
            "event_log": self.event_log,
            "decisions": self.decisions,
            "result": self.result,
            "last_error": self.last_error,
        }


class PokemonShowdownSessionService:
    """In-memory orchestration layer for autonomous Showdown sessions."""

    def __init__(self):
        self.sessions: dict[str, ShowdownSessionState] = {}
        self.connectors: dict[str, PokemonShowdownConnector] = {}
        self.agents: dict[str, PokemonShowdownBattleAgent] = {}

    def create_session(
        self,
        *,
        username: str,
        team: list[dict[str, Any]] | str | None,
        battle_format: str = "gen9vgc2024regg",
        mode: str = "balanced",
        login_assertion: str | None = None,
        auto_search: bool = False,
        connector: PokemonShowdownConnector | None = None,
    ) -> ShowdownSessionState:
        session_id = uuid4().hex
        connector = connector or PokemonShowdownConnector()
        format_info = pokemon_format_catalog.get(battle_format)
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
            status="searching" if auto_search else "ready",
            team=team,
            login_assertion=login_assertion,
        )
        if auto_search:
            state.command_log.extend(connector.build_ladder_search_messages(team, format_info.showdown_format))
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
                allow_tera=allow_tera,
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

        if commands:
            state.command_log.extend(commands)
        state.touch()
        return {
            "session": state.to_dict(),
            "events": [self._serialize_event(event) for event in events],
            "commands": commands,
            "decision": None if plan is None else plan.to_dict(),
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
        commands = connector.build_ladder_search_messages(state.team, state.showdown_format)
        state.command_log.extend(commands)
        state.status = "searching"
        state.touch()
        return commands

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

    def _serialize_event(self, event: ShowdownEvent) -> dict[str, Any]:
        return {
            "room_id": event.room_id,
            "event_type": event.event_type,
            "args": event.args,
            "raw": event.raw,
        }


pokemon_showdown_session_service = PokemonShowdownSessionService()
