"""
Pokemon API Schemas
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


# Species schemas
class SpeciesBase(BaseModel):
    id: int
    name: str
    name_zh: str
    types: List[str]
    base_stats: Dict[str, int]


class SpeciesResponse(SpeciesBase):
    abilities: List[str]
    hidden_ability: Optional[str]
    weight: float


# Move schemas
class MoveBase(BaseModel):
    name: str
    name_zh: str
    type: str
    category: str
    power: Optional[int]
    accuracy: Optional[int]


class MoveResponse(MoveBase):
    pp: int
    priority: int
    target: str


# Team schemas
class TeamPokemon(BaseModel):
    species: str
    name: Optional[str] = None
    level: int = 50
    ability: str
    item: str
    moves: List[str]
    stats: Optional[Dict[str, int]] = None


class TeamCreate(BaseModel):
    name: str
    format: str = "vgc2024"
    pokemon: List[TeamPokemon]


class TeamResponse(BaseModel):
    id: UUID
    agent_id: UUID
    name: str
    format: str
    pokemon_list: List[Dict[str, Any]]
    created_at: datetime


# Battle schemas
class BattleCreate(BaseModel):
    player1_team_id: UUID
    player2_team_id: Optional[UUID] = None
    battle_format: str = "vgc2024"


class BattleResponse(BaseModel):
    id: UUID
    battle_format: str
    player1_agent_id: UUID
    player2_agent_id: Optional[UUID]
    turns: int
    winner: Optional[int]
    battle_log: List[Dict[str, Any]]
    summary: Dict[str, Any]


class BattleStateResponse(BaseModel):
    battle_id: str
    turn: int
    phase: str
    weather: str
    trick_room: bool
    winner: Optional[int]
    player1: Dict[str, Any]
    player2: Dict[str, Any]


class BattleAction(BaseModel):
    pokemon_index: int
    action_type: str  # "move" or "switch"
    move_index: Optional[int] = None
    target: Optional[List[int]] = None
    switch_to: Optional[int] = None


class BattleTurnRequest(BaseModel):
    player1_actions: List[BattleAction]
    player2_actions: Optional[List[BattleAction]] = None


# Response schemas
class PokemonSpeciesList(BaseModel):
    species: List[SpeciesResponse]


class PokemonMoveList(BaseModel):
    moves: List[MoveResponse]


class TeamListResponse(BaseModel):
    teams: List[TeamResponse]


class BattleListResponse(BaseModel):
    battles: List[BattleResponse]
