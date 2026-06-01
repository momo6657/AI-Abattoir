"""Pokemon Showdown protocol connector skeleton.

This module intentionally keeps network operations optional. The parser and
message builder are testable without opening a live Pokemon Showdown session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ShowdownConnectionError(RuntimeError):
    """Raised when live Showdown connectivity is unavailable."""


@dataclass
class ShowdownEvent:
    room_id: str
    event_type: str
    args: list[str] = field(default_factory=list)
    raw: str = ""


class PokemonShowdownConnector:
    """Minimal connector for Pokemon Showdown rooms and battle messages."""

    def __init__(self, server_url: str = "wss://sim3.psim.us/showdown/websocket"):
        self.server_url = server_url
        self.websocket: Any | None = None
        self.current_room = ""

    def parse_message(self, payload: str) -> list[ShowdownEvent]:
        events: list[ShowdownEvent] = []
        room_id = self.current_room
        for raw_line in payload.splitlines():
            if not raw_line:
                continue
            if raw_line.startswith(">"):
                room_id = raw_line[1:]
                self.current_room = room_id
                continue
            if raw_line.startswith("|"):
                parts = raw_line.split("|")
                event_type = parts[1] if len(parts) > 1 else ""
                events.append(ShowdownEvent(room_id=room_id, event_type=event_type, args=parts[2:], raw=raw_line))
        return events

    def build_login_message(self, username: str, assertion: str) -> str:
        return f"|/trn {username},0,{assertion}"

    def build_search_message(self, battle_format: str = "gen9vgc2024regg") -> str:
        return f"|/search {battle_format}"

    def build_choose_move(self, room_id: str, move_slot: int, target: int | None = None) -> str:
        target_part = f" {target}" if target is not None else ""
        return f"{room_id}|/choose move {move_slot}{target_part}"

    def build_choose_switch(self, room_id: str, switch_slot: int) -> str:
        return f"{room_id}|/choose switch {switch_slot}"

    async def connect(self) -> None:
        try:
            import websockets  # type: ignore
        except ImportError as exc:
            raise ShowdownConnectionError(
                "Live Pokemon Showdown connection requires the optional 'websockets' package."
            ) from exc
        self.websocket = await websockets.connect(self.server_url)

    async def send(self, message: str) -> None:
        if not self.websocket:
            raise ShowdownConnectionError("Pokemon Showdown websocket is not connected.")
        await self.websocket.send(message)

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
            self.websocket = None


pokemon_showdown_connector = PokemonShowdownConnector()
