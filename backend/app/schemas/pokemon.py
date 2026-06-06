"""
Pokemon API Schemas
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
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


class ShowdownCommandRequest(BaseModel):
    action: str = Field(
        ...,
        description="Command kind: ladder_search, challenge, accept_challenge, reject_challenge, cancel_search, use_team, choose_team, choose_move, choose_switch, choose_multi, choose_default.",
    )
    battle_format: str = "gen9vgc2024regg"
    team: Optional[Union[List[Dict[str, Any]], str]] = None
    username: Optional[str] = None
    room_id: Optional[str] = None
    slots: Optional[List[int]] = None
    move_slot: Optional[int] = None
    switch_slot: Optional[int] = None
    target: Optional[int] = None
    request_id: Optional[int] = None
    modifier: Optional[str] = None
    choices: Optional[List[str]] = None


class ShowdownDecisionRequest(BaseModel):
    payload: Optional[str] = None
    request: Optional[Dict[str, Any]] = None
    room_id: Optional[str] = None
    mode: str = "balanced"
    team_size: Optional[int] = None
    active_pokemon: Optional[int] = None
    allow_tera: bool = True
    knowledge_context: Optional[Dict[str, Any]] = None
    learning_profile: Optional[Dict[str, Any]] = None
    team_context: Optional[List[Dict[str, Any]]] = None
    battlefield_context: Optional[Dict[str, Any]] = None


class PokemonTeamKnowledgeRequest(BaseModel):
    species: List[str]
    query_type: str = "species_usage"
    max_results: int = 3


class ShowdownSessionCreateRequest(BaseModel):
    username: str
    team: Optional[Union[List[Dict[str, Any]], str]] = None
    battle_format: str = "gen9vgc2024regg"
    mode: str = Field(
        "balanced",
        description="Battle policy mode: auto, balanced, aggressive, or defensive. auto selects from the learned Showdown profile.",
    )
    login_assertion: Optional[str] = None
    login_password: Optional[str] = None
    auto_login: bool = True
    auto_accept_challenges: bool = False
    auto_research_team: bool = False
    auto_search: bool = False


class ShowdownSessionMessageRequest(BaseModel):
    payload: str
    auto_respond: bool = True
    team_size: Optional[int] = None
    allow_tera: bool = True


class ShowdownSessionRunRequest(BaseModel):
    auto_respond: bool = True
    send_commands: bool = True
    team_size: Optional[int] = None
    allow_tera: bool = True
    max_messages: int = 50
    stop_on_finished: bool = True
    stop_on_error: bool = True


class ShowdownSessionAutopilotRequest(ShowdownSessionRunRequest):
    auto_search: bool = True
    close_on_finish: bool = False


class ShowdownSessionNextActionRequest(BaseModel):
    action: Optional[str] = Field(
        None,
        description="Recommended action to execute. If omitted, the first session next_actions item is used.",
    )
    max_messages: int = 50
    auto_search: bool = True
    send_commands: bool = True
    stop_on_finished: bool = True
    stop_on_error: bool = True
    max_results: int = 3


class ShowdownSessionSupervisorRequest(ShowdownSessionNextActionRequest):
    max_actions: int = Field(
        5,
        description="Maximum recommended actions the backend supervisor may execute in one request.",
    )
    allowed_actions: Optional[List[str]] = Field(
        None,
        description="Optional allow-list. The supervisor skips recommendations outside this set.",
    )
    stop_actions: Optional[List[str]] = Field(
        None,
        description="Optional action names that stop the supervisor immediately after they run.",
    )
    stop_on_new_session: bool = True


class ShowdownSessionMissionRequest(ShowdownSessionCreateRequest):
    start_action: Optional[str] = Field(
        None,
        description="Optional first supervisor action after creating the session.",
    )
    max_actions: int = Field(
        5,
        description="Maximum recommended actions the mission supervisor may execute after session creation.",
    )
    allowed_actions: Optional[List[str]] = None
    stop_actions: Optional[List[str]] = None
    max_messages: int = 50
    send_commands: bool = True
    stop_on_finished: bool = True
    stop_on_error: bool = True
    stop_on_new_session: bool = True
    max_results: int = 3
