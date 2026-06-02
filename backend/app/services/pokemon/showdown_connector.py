"""Pokemon Showdown protocol connector skeleton.

This module intentionally keeps network operations optional. The parser and
message builder are testable without opening a live Pokemon Showdown session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json
import re
import httpx


class ShowdownConnectionError(RuntimeError):
    """Raised when live Showdown connectivity is unavailable."""


@dataclass
class ShowdownEvent:
    room_id: str
    event_type: str
    args: list[str] = field(default_factory=list)
    raw: str = ""


@dataclass
class ShowdownBattleRequest:
    """Structured choice request from a Pokemon Showdown battle room."""

    room_id: str
    request_id: int | None
    active: list[dict[str, Any]] = field(default_factory=list)
    side: dict[str, Any] = field(default_factory=dict)
    force_switch: list[bool] = field(default_factory=list)
    wait: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def needs_choice(self) -> bool:
        return not self.wait and bool(self.team_preview or self.active or self.force_switch)

    @property
    def team_preview(self) -> bool:
        return bool(self.raw.get("teamPreview"))

    @property
    def max_team_size(self) -> int | None:
        value = self.raw.get("maxTeamSize")
        return int(value) if value is not None else None


class PokemonShowdownConnector:
    """Minimal connector for Pokemon Showdown rooms and battle messages."""

    def __init__(
        self,
        server_url: str = "wss://sim3.psim.us/showdown/websocket",
        login_url: str = "https://play.pokemonshowdown.com/action.php",
    ):
        self.server_url = server_url
        self.login_url = login_url
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

    def to_id(self, value: Any) -> str:
        """Convert names to Pokemon Showdown ID form."""
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    def build_login_message(self, username: str, assertion: str) -> str:
        return f"|/trn {username},0,{assertion}"

    def extract_challstr(self, events: list[ShowdownEvent]) -> str | None:
        for event in events:
            if event.event_type == "challstr":
                return "|".join(event.args)
        return None

    async def request_assertion(
        self,
        username: str,
        challstr: str,
        password: str | None = None,
    ) -> str:
        payload = {
            "act": "login" if password else "getassertion",
            "name": username,
            "challstr": challstr,
        }
        if password:
            payload["pass"] = password
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(self.login_url, data=payload)
            response.raise_for_status()
        text = response.text
        if text.startswith("]"):
            data = json.loads(text[1:])
            assertion = data.get("assertion")
            if not assertion:
                raise ShowdownConnectionError(data.get("actionsuccess") or "Pokemon Showdown login failed.")
            return assertion
        if not text:
            raise ShowdownConnectionError("Pokemon Showdown returned an empty assertion.")
        return text

    def build_search_message(self, battle_format: str = "gen9vgc2024regg") -> str:
        return f"|/search {battle_format}"

    def build_cancel_search_message(self) -> str:
        return "|/cancelsearch"

    def build_use_team_message(self, team: list[dict[str, Any]] | str | None) -> str:
        packed_team = "null" if team is None else team if isinstance(team, str) else self.pack_team(team)
        return f"|/utm {packed_team}"

    def build_ladder_search_messages(
        self,
        team: list[dict[str, Any]] | str | None,
        battle_format: str = "gen9vgc2024regg",
    ) -> list[str]:
        return [self.build_use_team_message(team), self.build_search_message(battle_format)]

    def build_challenge_messages(
        self,
        username: str,
        battle_format: str,
        team: list[dict[str, Any]] | str | None,
    ) -> list[str]:
        return [self.build_use_team_message(team), f"|/challenge {username}, {battle_format}"]

    def build_accept_challenge_messages(
        self,
        username: str,
        team: list[dict[str, Any]] | str | None,
    ) -> list[str]:
        return [self.build_use_team_message(team), f"|/accept {username}"]

    def build_reject_challenge_message(self, username: str) -> str:
        return f"|/reject {username}"

    def build_choose_team(self, room_id: str, slots: list[int], request_id: int | None = None) -> str:
        if any(slot < 1 for slot in slots):
            raise ValueError("Pokemon Showdown team preview slots are 1-based.")
        team_spec = "".join(str(slot) for slot in slots) if len(slots) <= 9 else ", ".join(str(slot) for slot in slots)
        return self._build_choose(room_id, f"team {team_spec}", request_id)

    def build_choose_default(self, room_id: str, request_id: int | None = None) -> str:
        return self._build_choose(room_id, "default", request_id)

    def build_choose_move(
        self,
        room_id: str,
        move_slot: int,
        target: int | None = None,
        request_id: int | None = None,
        modifier: str | None = None,
    ) -> str:
        if move_slot < 1:
            raise ValueError("Pokemon Showdown move slots are 1-based.")
        target_part = f" {target}" if target is not None else ""
        modifier_part = f" {modifier}" if modifier else ""
        return self._build_choose(room_id, f"move {move_slot}{target_part}{modifier_part}", request_id)

    def build_choose_switch(self, room_id: str, switch_slot: int, request_id: int | None = None) -> str:
        if switch_slot < 1:
            raise ValueError("Pokemon Showdown switch slots are 1-based.")
        return self._build_choose(room_id, f"switch {switch_slot}", request_id)

    def build_choose_multi(self, room_id: str, choices: list[str], request_id: int | None = None) -> str:
        return self._build_choose(room_id, ", ".join(choices), request_id)

    def _build_choose(self, room_id: str, choice: str, request_id: int | None = None) -> str:
        request_part = f"|{request_id}" if request_id is not None else ""
        return f"{room_id}|/choose {choice}{request_part}"

    def pack_team(self, pokemon: list[dict[str, Any]]) -> str:
        """Convert local team dictionaries into Pokemon Showdown packed format."""
        return "]".join(self._pack_set(member) for member in pokemon)

    def _pack_set(self, pokemon: dict[str, Any]) -> str:
        species = pokemon.get("species") or pokemon.get("name") or "Unknown"
        nickname = pokemon.get("name") or species
        species_field = "" if self.to_id(nickname) == self.to_id(species) else species
        item = self.to_id(pokemon.get("item", ""))
        ability = self.to_id(pokemon.get("ability", ""))
        moves = ",".join(self.to_id(move.get("name") if isinstance(move, dict) else move) for move in pokemon.get("moves", []))
        nature = pokemon.get("nature", "")
        evs = self._pack_stats(pokemon.get("evs", {}), default=0)
        gender = pokemon.get("gender", "")
        ivs = self._pack_stats(pokemon.get("ivs", {}), default=31)
        shiny = "S" if pokemon.get("shiny") else ""
        level = "" if int(pokemon.get("level", 50)) == 100 else str(int(pokemon.get("level", 50)))
        misc = self._pack_misc(pokemon)
        return "|".join([
            str(nickname),
            str(species_field),
            item,
            ability,
            moves,
            str(nature),
            evs,
            str(gender),
            ivs,
            shiny,
            level,
            misc,
        ])

    def _pack_stats(self, stats: dict[str, Any], default: int) -> str:
        order = ["hp", "atk", "def", "spa", "spd", "spe"]
        values = []
        for stat in order:
            value = stats.get(stat, default)
            values.append("" if int(value) == default else str(int(value)))
        while values and values[-1] == "":
            values.pop()
        return ",".join(values)

    def _pack_misc(self, pokemon: dict[str, Any]) -> str:
        values = [
            "" if int(pokemon.get("happiness", 255)) == 255 else str(int(pokemon.get("happiness", 255))),
            self.to_id(pokemon.get("pokeball", "")),
            pokemon.get("hidden_power_type", ""),
            "G" if pokemon.get("gigantamax") else "",
            "" if int(pokemon.get("dynamax_level", 10)) == 10 else str(int(pokemon.get("dynamax_level", 10))),
            pokemon.get("tera_type", ""),
        ]
        while values and values[-1] == "":
            values.pop()
        return ",".join(str(value) for value in values)

    def parse_battle_request(self, events: list[ShowdownEvent]) -> ShowdownBattleRequest | None:
        for event in reversed(events):
            if event.event_type != "request" or not event.args:
                continue
            try:
                payload = json.loads(event.args[0])
            except json.JSONDecodeError as exc:
                raise ShowdownConnectionError(f"Invalid Pokemon Showdown request payload: {event.args[0][:120]}") from exc
            return ShowdownBattleRequest(
                room_id=event.room_id,
                request_id=payload.get("rqid"),
                active=payload.get("active") or [],
                side=payload.get("side") or {},
                force_switch=payload.get("forceSwitch") or [],
                wait=bool(payload.get("wait")),
                raw=payload,
            )
        return None

    def parse_search_update(self, events: list[ShowdownEvent]) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.event_type != "updatesearch" or not event.args:
                continue
            return json.loads(event.args[0])
        return None

    def parse_challenge_update(self, events: list[ShowdownEvent]) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.event_type != "updatechallenges" or not event.args:
                continue
            return json.loads(event.args[0])
        return None

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

    async def receive(self) -> str:
        if not self.websocket:
            raise ShowdownConnectionError("Pokemon Showdown websocket is not connected.")
        return await self.websocket.recv()

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
            self.websocket = None


pokemon_showdown_connector = PokemonShowdownConnector()
