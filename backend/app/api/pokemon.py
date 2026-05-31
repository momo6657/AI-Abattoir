"""
Pokemon Battle API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.schemas.pokemon import (
    SpeciesResponse,
    MoveResponse,
    TeamCreate,
    TeamResponse,
    BattleCreate,
    BattleResponse,
    BattleStateResponse,
    BattleTurnRequest,
)
from app.models.pokemon import (
    PokemonSpecies,
    PokemonMove,
    PokemonTeam,
    PokemonBattle,
)
from app.services.pokemon.battle_engine import BattleEngine
from app.services.pokemon.data_loader import PokemonDataLoader

router = APIRouter(prefix="/api/pokemon", tags=["pokemon"])


# Species endpoints
@router.get("/species", response_model=List[SpeciesResponse])
async def get_species_list(db: AsyncSession = Depends(get_db)):
    """Get list of all Pokemon species"""
    result = await db.execute(select(PokemonSpecies))
    species = result.scalars().all()
    return species


@router.get("/species/{species_id}", response_model=SpeciesResponse)
async def get_species(species_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific Pokemon species by ID"""
    result = await db.execute(
        select(PokemonSpecies).where(PokemonSpecies.id == species_id)
    )
    species = result.scalar_one_or_none()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")
    return species


# Move endpoints
@router.get("/moves", response_model=List[MoveResponse])
async def get_moves_list(db: AsyncSession = Depends(get_db)):
    """Get list of all moves"""
    result = await db.execute(select(PokemonMove))
    moves = result.scalars().all()
    return moves


# Team endpoints
@router.get("/teams", response_model=List[TeamResponse])
async def get_teams(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all teams for an agent"""
    result = await db.execute(
        select(PokemonTeam).where(PokemonTeam.agent_id == agent_id)
    )
    teams = result.scalars().all()
    return teams


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    agent_id: UUID,
    team_data: TeamCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new team"""
    team = PokemonTeam(
        agent_id=agent_id,
        name=team_data.name,
        format=team_data.format,
        pokemon_list=[p.model_dump() for p in team_data.pokemon],
        source="custom",
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


@router.get("/teams/{team_id}", response_model=TeamResponse)
async def get_team(team_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific team"""
    result = await db.execute(
        select(PokemonTeam).where(PokemonTeam.id == team_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a team"""
    result = await db.execute(
        select(PokemonTeam).where(PokemonTeam.id == team_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    await db.delete(team)
    await db.commit()


# Battle endpoints
@router.post("/battles", response_model=BattleResponse, status_code=status.HTTP_201_CREATED)
async def create_battle(
    battle_data: BattleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new battle"""
    # Get teams
    result1 = await db.execute(
        select(PokemonTeam).where(PokemonTeam.id == battle_data.player1_team_id)
    )
    team1 = result1.scalar_one_or_none()
    if not team1:
        raise HTTPException(status_code=404, detail="Player 1 team not found")

    if battle_data.player2_team_id:
        result2 = await db.execute(
            select(PokemonTeam).where(PokemonTeam.id == battle_data.player2_team_id)
        )
        team2 = result2.scalar_one_or_none()
        if not team2:
            raise HTTPException(status_code=404, detail="Player 2 team not found")
    else:
        # Create AI team from template
        team2 = team1  # Simplified: use same team for now

    # Create battle record
    battle = PokemonBattle(
        battle_format=battle_data.battle_format,
        player1_agent_id=team1.agent_id,
        player2_agent_id=team2.agent_id,
        player1_team_id=team1.id,
        player2_team_id=team2.id,
        status="in_progress",
    )
    db.add(battle)
    await db.commit()
    await db.refresh(battle)

    # Initialize battle engine
    engine = BattleEngine()
    battle_state = engine.create_battle(
        team1.pokemon_list,
        team2.pokemon_list,
        battle.battle_format,
    )

    # Store initial state
    battle.state = battle_state.to_dict()
    await db.commit()

    return battle


@router.get("/battles/{battle_id}", response_model=BattleResponse)
async def get_battle(battle_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get battle information"""
    result = await db.execute(
        select(PokemonBattle).where(PokemonBattle.id == battle_id)
    )
    battle = result.scalar_one_or_none()
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    return battle


@router.get("/battles/{battle_id}/state", response_model=BattleStateResponse)
async def get_battle_state(battle_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get current battle state"""
    result = await db.execute(
        select(PokemonBattle).where(PokemonBattle.id == battle_id)
    )
    battle = result.scalar_one_or_none()
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")

    if not battle.state:
        raise HTTPException(status_code=400, detail="Battle not initialized")

    return battle.state


@router.post("/battles/{battle_id}/turn")
async def submit_turn(
    battle_id: UUID,
    turn_data: BattleTurnRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit actions for a turn"""
    result = await db.execute(
        select(PokemonBattle).where(PokemonBattle.id == battle_id)
    )
    battle = result.scalar_one_or_none()
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")

    if not battle.state:
        raise HTTPException(status_code=400, detail="Battle not initialized")

    # Execute turn
    engine = BattleEngine()
    battle_state = engine.from_dict(battle.state)

    turn_result = engine.execute_turn(
        battle_state,
        [a.model_dump() for a in turn_data.player1_actions],
        [a.model_dump() for a in turn_data.player2_actions] if turn_data.player2_actions else [],
    )

    # Update battle state
    battle.state = turn_result["state"]
    battle.turn = turn_result["turn"]

    if turn_result["winner"]:
        battle.status = "finished"
        battle.winner = turn_result["winner"]

    await db.commit()

    return turn_result


# Data loading endpoint
@router.post("/init-data")
async def initialize_pokemon_data(db: AsyncSession = Depends(get_db)):
    """Initialize Pokemon data from JSON files"""
    loader = PokemonDataLoader(db)
    counts = await loader.load_all()
    return {"loaded": counts}
