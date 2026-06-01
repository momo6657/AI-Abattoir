"""
Battle State - Represents the complete state of a Pokemon battle
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import copy


class BattlePhase(Enum):
    TEAM_PREVIEW = "team_preview"
    BATTLE = "battle"
    FINISHED = "finished"


class Weather(Enum):
    NONE = "none"
    SUN = "sun"
    RAIN = "rain"
    SAND = "sand"
    HAIL = "hail"
    SNOW = "snow"


@dataclass
class PokemonState:
    """State of a single Pokemon in battle"""
    species: str
    name: str
    level: int = 50
    types: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)  # hp, atk, def, spa, spd, spe
    current_hp: int = 0
    max_hp: int = 0
    moves: List[Dict[str, Any]] = field(default_factory=list)
    ability: str = ""
    item: str = ""
    status: Optional[str] = None  # poison, burn, paralysis, sleep, freeze
    stat_stages: Dict[str, int] = field(default_factory=lambda: {
        "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0, "accuracy": 0, "evasion": 0
    })
    is_fainted: bool = False
    is_active: bool = False
    position: int = 0  # 0 or 1 for doubles
    has_tera: bool = True
    tera_type: Optional[str] = None
    volatiles: Dict[str, Any] = field(default_factory=dict)  # substitute, protect count, etc.
    turn_charge: Dict[str, bool] = field(default_factory=dict)  # for 2-turn moves

    def hp_percent(self) -> float:
        if self.max_hp == 0:
            return 0.0
        return self.current_hp / self.max_hp

    def can_move(self) -> bool:
        return not self.is_fainted and self.status not in ["freeze", "sleep"]


@dataclass
class PlayerState:
    """State of a player's team"""
    agent_id: str
    team: List[PokemonState] = field(default_factory=list)
    active: List[int] = field(default_factory=list)  # indices of active Pokemon
    can_tera: bool = True

    def get_active_pokemon(self) -> List[PokemonState]:
        return [self.team[i] for i in self.active if i < len(self.team)]

    def get_bench_pokemon(self) -> List[PokemonState]:
        return [p for i, p in enumerate(self.team) if i not in self.active and not p.is_fainted]

    def all_fainted(self) -> bool:
        return all(p.is_fainted for p in self.team)


@dataclass
class BattleState:
    """Complete battle state"""
    battle_id: str
    player1: PlayerState
    player2: PlayerState
    turn: int = 0
    phase: BattlePhase = BattlePhase.TEAM_PREVIEW
    weather: Weather = Weather.NONE
    weather_turns: int = 0
    trick_room: bool = False
    trick_room_turns: int = 0
    battle_log: List[Dict[str, Any]] = field(default_factory=list)
    winner: Optional[int] = None  # 1 or 2 or None

    def add_log(self, event: str, data: Dict[str, Any] = None):
        entry = {"turn": self.turn, "event": event}
        if data:
            entry["data"] = data
        self.battle_log.append(entry)

    def is_over(self) -> bool:
        return self.phase == BattlePhase.FINISHED

    def check_winner(self) -> Optional[int]:
        if self.player1.all_fainted():
            self.winner = 2
            self.phase = BattlePhase.FINISHED
            return 2
        if self.player2.all_fainted():
            self.winner = 1
            self.phase = BattlePhase.FINISHED
            return 1
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "battle_id": self.battle_id,
            "turn": self.turn,
            "phase": self.phase.value,
            "weather": self.weather.value,
            "trick_room": self.trick_room,
            "winner": self.winner,
            "player1": self._player_to_dict(self.player1),
            "player2": self._player_to_dict(self.player2),
        }

    def _player_to_dict(self, player: PlayerState) -> Dict[str, Any]:
        return {
            "agent_id": player.agent_id,
            "active": [self._pokemon_to_dict(p) for p in player.get_active_pokemon()],
            "bench": [self._pokemon_to_dict(p) for p in player.get_bench_pokemon()],
            "can_tera": player.can_tera,
        }

    def _pokemon_to_dict(self, pokemon: PokemonState) -> Dict[str, Any]:
        return {
            "species": pokemon.species,
            "name": pokemon.name,
            "level": pokemon.level,
            "types": pokemon.types,
            "current_hp": pokemon.current_hp,
            "max_hp": pokemon.max_hp,
            "hp_percent": pokemon.hp_percent(),
            "status": pokemon.status,
            "is_fainted": pokemon.is_fainted,
            "is_active": pokemon.is_active,
            "stats": pokemon.stats,
            "moves": pokemon.moves,
            "ability": pokemon.ability,
            "item": pokemon.item,
            "position": pokemon.position,
            "stat_stages": pokemon.stat_stages,
            "has_tera": pokemon.has_tera,
            "tera_type": pokemon.tera_type,
        }

    def deep_copy(self) -> "BattleState":
        return copy.deepcopy(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BattleState":
        """Rehydrate a BattleState previously produced by to_dict()."""
        return cls(
            battle_id=data["battle_id"],
            player1=cls._player_from_dict(data["player1"]),
            player2=cls._player_from_dict(data["player2"]),
            turn=data.get("turn", 0),
            phase=BattlePhase(data.get("phase", BattlePhase.BATTLE.value)),
            weather=Weather(data.get("weather", Weather.NONE.value)),
            trick_room=data.get("trick_room", False),
            battle_log=data.get("battle_log", []),
            winner=data.get("winner"),
        )

    @staticmethod
    def _player_from_dict(data: Dict[str, Any]) -> PlayerState:
        active_payload = data.get("active", [])
        team_payload = data.get("team")
        if team_payload is not None and all(isinstance(item, int) for item in active_payload):
            team = [
                BattleState._pokemon_from_dict(pokemon_data, idx in set(active_payload))
                for idx, pokemon_data in enumerate(team_payload)
            ]
        else:
            bench_payload = data.get("bench", [])
            combined = active_payload + bench_payload
            team = [
                BattleState._pokemon_from_dict(pokemon_data, idx in range(len(active_payload)))
                for idx, pokemon_data in enumerate(combined)
            ]
        return PlayerState(
            agent_id=data.get("agent_id", ""),
            team=team,
            active=[i for i, pokemon in enumerate(team) if pokemon.is_active],
            can_tera=data.get("can_tera", True),
        )

    @staticmethod
    def _pokemon_from_dict(data: Dict[str, Any], default_active: bool) -> PokemonState:
        return PokemonState(
            species=data.get("species", "Unknown"),
            name=data.get("name", data.get("species", "Unknown")),
            level=data.get("level", 50),
            types=data.get("types", ["Normal"]),
            stats=data.get("stats", {}),
            current_hp=data.get("current_hp", data.get("max_hp", 0)),
            max_hp=data.get("max_hp", 0),
            moves=data.get("moves", []),
            ability=data.get("ability", ""),
            item=data.get("item", ""),
            status=data.get("status"),
            stat_stages=data.get("stat_stages", {
                "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0, "accuracy": 0, "evasion": 0
            }),
            is_fainted=data.get("is_fainted", False),
            is_active=data.get("is_active", default_active),
            position=data.get("position", 0),
            has_tera=data.get("has_tera", True),
            tera_type=data.get("tera_type"),
        )
