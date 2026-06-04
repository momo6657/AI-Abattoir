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
    PokemonTeamKnowledgeRequest,
    ShowdownCommandRequest,
    ShowdownDecisionRequest,
    ShowdownSessionAutopilotRequest,
    ShowdownSessionCreateRequest,
    ShowdownSessionMessageRequest,
    ShowdownSessionRunRequest,
)
from app.models.pokemon import (
    PokemonSpecies,
    PokemonMove,
    PokemonTeam,
    PokemonBattle,
)
from app.models.agent import Agent
from app.services.pokemon.battle_engine import BattleEngine
from app.services.pokemon.data_loader import PokemonDataLoader
from app.services.pokemon.knowledge_service import pokemon_knowledge_service
from app.services.pokemon.team_builder import pokemon_team_builder
from app.services.pokemon.battle_analysis import pokemon_battle_analysis_service
from app.services.pokemon.format_catalog import pokemon_format_catalog
from app.services.pokemon.showdown_connector import ShowdownConnectionError, pokemon_showdown_connector
from app.services.pokemon.showdown_battle_agent import pokemon_showdown_battle_agent
from app.services.pokemon.showdown_session import pokemon_showdown_session_service
from app.services.pokemon.showdown_learning_store import pokemon_showdown_learning_store

router = APIRouter(prefix="/pokemon", tags=["pokemon"])


# Data initialization endpoint
@router.post("/init")
async def init_pokemon_data(db: AsyncSession = Depends(get_db)):
    """Initialize Pokemon data from JSON files"""
    loader = PokemonDataLoader(db)
    counts = await loader.load_all()
    return {
        "species_loaded": counts.get("species", 0),
        "moves_loaded": counts.get("moves", 0),
        "abilities_loaded": counts.get("abilities", 0),
        "items_loaded": counts.get("items", 0),
    }


# Species endpoints
@router.get("/formats")
async def list_pokemon_formats():
    """List supported Pokemon battle format metadata."""
    return [battle_format.to_dict() for battle_format in pokemon_format_catalog.list_formats()]


@router.get("/formats/{format_id}")
async def get_pokemon_format(format_id: str):
    """Get one Pokemon battle format metadata item."""
    try:
        return pokemon_format_catalog.get(format_id).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@router.post("/teams/build", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def build_team_for_agent(
    agent_id: UUID,
    battle_format: str = "vgc2024",
    db: AsyncSession = Depends(get_db),
):
    """Build a team for an agent based on its Pokemon level/playstyle."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        return await pokemon_team_builder.build_for_agent(db, agent, battle_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/battles/history", response_model=List[BattleResponse])
async def get_battle_history(
    agent_id: UUID | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get Pokemon battle history, optionally scoped to one agent."""
    query = select(PokemonBattle).order_by(PokemonBattle.created_at.desc()).limit(limit)
    if agent_id:
        query = (
            select(PokemonBattle)
            .where((PokemonBattle.player1_agent_id == agent_id) | (PokemonBattle.player2_agent_id == agent_id))
            .order_by(PokemonBattle.created_at.desc())
            .limit(limit)
        )
    result = await db.execute(query)
    return list(result.scalars().all())


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
        turns=0,
        battle_log=[],
        summary={},
    )
    db.add(battle)
    await db.commit()
    await db.refresh(battle)

    # Initialize battle engine
    engine = BattleEngine()
    battle_state = engine.create_battle(
        str(battle.id),  # battle_id
        team1.pokemon_list,  # p1_team
        team2.pokemon_list,  # p2_team
        str(team1.agent_id),  # p1_agent_id
        str(team2.agent_id),  # p2_agent_id
    )

    # Store initial battle state
    battle.battle_log = battle_state.battle_log
    battle.summary = {
        "battle_id": str(battle.id),
        "turn": battle_state.turn,
        "state": battle_state.to_dict(),
        "status": "in_progress",
        "player1_active": battle_state.player1.active,
        "player2_active": battle_state.player2.active,
    }
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

    state = (battle.summary or {}).get("state") if isinstance(battle.summary, dict) else None
    if not state:
        state = getattr(battle, "state", None)
    if not state:
        raise HTTPException(status_code=400, detail="Battle not initialized")

    return state


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

    state_payload = (battle.summary or {}).get("state") if isinstance(battle.summary, dict) else None
    if not state_payload:
        state_payload = getattr(battle, "state", None)
    if not state_payload:
        raise HTTPException(status_code=400, detail="Battle not initialized")

    # Execute turn
    engine = BattleEngine()
    battle_state = engine.from_dict(state_payload)

    next_state = engine.execute_turn(
        battle_state,
        [a.model_dump() for a in turn_data.player1_actions],
        [a.model_dump() for a in turn_data.player2_actions] if turn_data.player2_actions else [],
    )

    # Update battle state
    turn_result = next_state.to_dict()
    turn_result["battle_log"] = next_state.battle_log
    if not isinstance(battle.summary, dict):
        battle.summary = {}
    battle.summary["state"] = turn_result
    battle.battle_log = next_state.battle_log
    battle.turns = next_state.turn

    if next_state.winner:
        battle.winner = next_state.winner
        battle.summary["status"] = "finished"
    else:
        battle.summary["status"] = "in_progress"
        battle.winner = next_state.winner

    await db.commit()

    return turn_result


@router.get("/battles/{battle_id}/analysis")
async def analyze_battle(battle_id: UUID, db: AsyncSession = Depends(get_db)):
    """Analyze a battle log and return summary statistics."""
    battle = await db.get(PokemonBattle, battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    return pokemon_battle_analysis_service.summarize(battle.battle_log or [])


@router.post("/battles/{battle_id}/finalize")
async def finalize_battle(
    battle_id: UUID,
    winner_agent_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Finalize a Pokemon battle and record evolution experience."""
    battle = await db.get(PokemonBattle, battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    return await pokemon_battle_analysis_service.finalize_battle(db, battle, winner_agent_id)


@router.get("/knowledge/search")
async def search_knowledge(
    query_type: str,
    query_key: str,
    max_results: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """Search Pokemon knowledge sources with database caching."""
    return await pokemon_knowledge_service.search(db, query_type, query_key, max_results)


@router.post("/knowledge/team")
async def search_team_knowledge(
    payload: PokemonTeamKnowledgeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Batch-search knowledge for a Showdown team and return a compact team context."""
    if not payload.species:
        raise HTTPException(status_code=400, detail="species is required.")
    if payload.max_results < 1 or payload.max_results > 10:
        raise HTTPException(status_code=400, detail="max_results must be between 1 and 10.")
    return await pokemon_knowledge_service.search_team(
        db,
        payload.species,
        query_type=payload.query_type,
        max_results=payload.max_results,
    )


@router.post("/showdown/parse")
async def parse_showdown_message(payload: dict):
    """Parse raw Pokemon Showdown protocol payload into structured events."""
    raw = payload.get("payload", "")
    events = pokemon_showdown_connector.parse_message(raw)
    try:
        battle_request = pokemon_showdown_connector.parse_battle_request(events)
        search = pokemon_showdown_connector.parse_search_update(events)
        challenges = pokemon_showdown_connector.parse_challenge_update(events)
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "events": [
            {"room_id": event.room_id, "event_type": event.event_type, "args": event.args, "raw": event.raw}
            for event in events
        ],
        "battle_request": None if battle_request is None else {
            "room_id": battle_request.room_id,
            "request_id": battle_request.request_id,
            "active": battle_request.active,
            "side": battle_request.side,
            "force_switch": battle_request.force_switch,
            "wait": battle_request.wait,
            "team_preview": battle_request.team_preview,
            "max_team_size": battle_request.max_team_size,
            "needs_choice": battle_request.needs_choice,
            "raw": battle_request.raw,
        },
        "search": search,
        "challenges": challenges,
    }


@router.post("/showdown/commands")
async def build_showdown_commands(payload: ShowdownCommandRequest):
    """Build Pokemon Showdown protocol commands for agent orchestration."""
    action = payload.action
    try:
        if action == "ladder_search":
            commands = pokemon_showdown_connector.build_ladder_search_messages(payload.team, payload.battle_format)
        elif action == "challenge":
            username = _required(payload.username, "username")
            commands = pokemon_showdown_connector.build_challenge_messages(username, payload.battle_format, payload.team)
        elif action == "accept_challenge":
            username = _required(payload.username, "username")
            commands = pokemon_showdown_connector.build_accept_challenge_messages(username, payload.team)
        elif action == "reject_challenge":
            username = _required(payload.username, "username")
            commands = [pokemon_showdown_connector.build_reject_challenge_message(username)]
        elif action == "cancel_search":
            commands = [pokemon_showdown_connector.build_cancel_search_message()]
        elif action == "use_team":
            commands = [pokemon_showdown_connector.build_use_team_message(payload.team)]
        elif action == "choose_team":
            commands = [pokemon_showdown_connector.build_choose_team(
                _required(payload.room_id, "room_id"),
                payload.slots or _raise_missing("slots"),
                payload.request_id,
            )]
        elif action == "choose_move":
            commands = [pokemon_showdown_connector.build_choose_move(
                _required(payload.room_id, "room_id"),
                payload.move_slot if payload.move_slot is not None else _raise_missing("move_slot"),
                payload.target,
                payload.request_id,
                payload.modifier,
            )]
        elif action == "choose_switch":
            commands = [pokemon_showdown_connector.build_choose_switch(
                _required(payload.room_id, "room_id"),
                payload.switch_slot if payload.switch_slot is not None else _raise_missing("switch_slot"),
                payload.request_id,
            )]
        elif action == "choose_multi":
            commands = [pokemon_showdown_connector.build_choose_multi(
                _required(payload.room_id, "room_id"),
                payload.choices or _raise_missing("choices"),
                payload.request_id,
            )]
        elif action == "choose_default":
            commands = [pokemon_showdown_connector.build_choose_default(_required(payload.room_id, "room_id"), payload.request_id)]
        else:
            raise ValueError(f"Unsupported Showdown command action: {action}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"commands": commands}


@router.post("/showdown/decision")
async def plan_showdown_decision(payload: ShowdownDecisionRequest):
    """Plan the next autonomous Pokemon Showdown battle choice."""
    try:
        if payload.payload is not None:
            events, request, plan = pokemon_showdown_battle_agent.plan_from_payload(
                payload.payload,
                mode=payload.mode,
                team_size=payload.team_size,
                active_pokemon=payload.active_pokemon,
                allow_tera=payload.allow_tera,
                knowledge_context=payload.knowledge_context,
                learning_profile=payload.learning_profile,
                team_context=payload.team_context,
                battlefield_context=payload.battlefield_context,
            )
            return {
                "events": [
                    {"room_id": event.room_id, "event_type": event.event_type, "args": event.args, "raw": event.raw}
                    for event in events
                ],
                "request": None if request is None else request.raw,
                "plan": plan.to_dict(),
            }
        if payload.request is not None:
            room_id = _required(payload.room_id, "room_id")
            plan = pokemon_showdown_battle_agent.plan_from_raw_request(
                payload.request,
                room_id,
                mode=payload.mode,
                team_size=payload.team_size,
                active_pokemon=payload.active_pokemon,
                allow_tera=payload.allow_tera,
                knowledge_context=payload.knowledge_context,
                learning_profile=payload.learning_profile,
                team_context=payload.team_context,
                battlefield_context=payload.battlefield_context,
            )
            return {"events": [], "request": payload.request, "plan": plan.to_dict()}
    except (ShowdownConnectionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail="payload or request is required.")


@router.post("/showdown/sessions")
async def create_showdown_session(payload: ShowdownSessionCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create an autonomous Pokemon Showdown session state machine."""
    try:
        resolved_mode, mode_source, mode_recommendation, learning_profile = await _resolve_showdown_mode(
            db,
            username=payload.username,
            battle_format=payload.battle_format,
            requested_mode=payload.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session = pokemon_showdown_session_service.create_session(
        username=payload.username,
        team=payload.team,
        battle_format=payload.battle_format,
        mode=resolved_mode,
        requested_mode=payload.mode,
        mode_source=mode_source,
        mode_recommendation=mode_recommendation,
        login_assertion=payload.login_assertion,
        login_password=payload.login_password,
        auto_login=payload.auto_login,
        auto_accept_challenges=payload.auto_accept_challenges,
        auto_research_team=payload.auto_research_team,
        auto_search=payload.auto_search,
        learning_profile=learning_profile,
    )
    if payload.auto_research_team and session.team_species:
        context = await pokemon_knowledge_service.search_team(
            db,
            session.team_species,
            query_type="species_usage",
            max_results=3,
        )
        session = pokemon_showdown_session_service.attach_knowledge_context(session.session_id, context)
    return session.to_dict()


@router.get("/showdown/learning/profiles")
async def list_showdown_learning_profiles(db: AsyncSession = Depends(get_db)):
    """List learned Pokemon Showdown session performance profiles."""
    return await pokemon_showdown_learning_store.list_profiles(db)


@router.get("/showdown/learning/profile")
async def get_showdown_learning_profile(
    username: str,
    battle_format: str = "vgc2024",
    db: AsyncSession = Depends(get_db),
):
    """Get learned Showdown performance stats for one user and format."""
    try:
        format_info = pokemon_format_catalog.get(battle_format)
        return await pokemon_showdown_learning_store.profile(db, username=username, battle_format=format_info.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/showdown/sessions")
async def list_showdown_sessions():
    """List in-memory Pokemon Showdown automation sessions."""
    return [session.to_dict() for session in pokemon_showdown_session_service.list_sessions()]


@router.get("/showdown/sessions/{session_id}/analysis")
async def analyze_showdown_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Analyze one Pokemon Showdown automation session event log."""
    try:
        analysis = pokemon_showdown_session_service.analyze_session(session_id)
        session = pokemon_showdown_session_service.get_session(session_id)
        if session:
            await _persist_showdown_learning(db, {"session": session.to_dict()})
        return analysis
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/showdown/sessions/{session_id}/knowledge")
async def research_showdown_session_team(
    session_id: str,
    max_results: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """Research and attach knowledge context for the current Showdown session team."""
    session = pokemon_showdown_session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Pokemon Showdown session not found")
    if not session.team_species:
        raise HTTPException(status_code=400, detail="Showdown session has no team species to research.")
    if max_results < 1 or max_results > 10:
        raise HTTPException(status_code=400, detail="max_results must be between 1 and 10.")
    context = await pokemon_knowledge_service.search_team(
        db,
        session.team_species,
        query_type="species_usage",
        max_results=max_results,
    )
    updated = pokemon_showdown_session_service.attach_knowledge_context(session_id, context)
    return {"knowledge_context": context, "session": updated.to_dict()}


@router.get("/showdown/sessions/{session_id}")
async def get_showdown_session(session_id: str):
    """Get a Pokemon Showdown automation session."""
    session = pokemon_showdown_session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Pokemon Showdown session not found")
    return session.to_dict()


@router.post("/showdown/sessions/{session_id}/search")
async def start_showdown_ladder_search(session_id: str):
    """Build and record ladder search commands for an existing session."""
    try:
        commands = pokemon_showdown_session_service.start_ladder_search(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session = pokemon_showdown_session_service.get_session(session_id)
    return {"commands": commands, "session": session.to_dict() if session else None}


@router.post("/showdown/sessions/{session_id}/cancel-search")
async def cancel_showdown_ladder_search(session_id: str):
    """Build and record a Showdown cancel-search command for an existing session."""
    try:
        commands = pokemon_showdown_session_service.cancel_ladder_search(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session = pokemon_showdown_session_service.get_session(session_id)
    return {"commands": commands, "session": session.to_dict() if session else None}


@router.post("/showdown/sessions/{session_id}/accept-challenge")
async def accept_showdown_challenge(session_id: str, username: str | None = None):
    """Queue commands to accept an incoming Pokemon Showdown challenge."""
    try:
        commands = pokemon_showdown_session_service.accept_challenge(session_id, username)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = pokemon_showdown_session_service.get_session(session_id)
    return {"commands": commands, "session": session.to_dict() if session else None}


@router.post("/showdown/sessions/{session_id}/reject-challenge")
async def reject_showdown_challenge(session_id: str, username: str | None = None):
    """Queue a command to reject an incoming Pokemon Showdown challenge."""
    try:
        commands = pokemon_showdown_session_service.reject_challenge(session_id, username)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = pokemon_showdown_session_service.get_session(session_id)
    return {"commands": commands, "session": session.to_dict() if session else None}


@router.post("/showdown/sessions/{session_id}/flush")
async def flush_showdown_session_commands(session_id: str):
    """Send all queued Pokemon Showdown commands over an already connected websocket."""
    try:
        sent = await pokemon_showdown_session_service.flush_pending_commands(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = pokemon_showdown_session_service.get_session(session_id)
    return {"sent": sent, "session": session.to_dict() if session else None}


@router.post("/showdown/sessions/{session_id}/connect")
async def connect_showdown_session(session_id: str, send_pending: bool = True):
    """Connect a Showdown session websocket and optionally flush queued commands."""
    try:
        return await pokemon_showdown_session_service.connect_session(session_id, send_pending=send_pending)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/showdown/sessions/{session_id}/message")
async def process_showdown_session_message(
    session_id: str,
    payload: ShowdownSessionMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Process Showdown protocol payload and return commands to send back."""
    try:
        result = pokemon_showdown_session_service.process_payload(
            session_id,
            payload.payload,
            auto_respond=payload.auto_respond,
            team_size=payload.team_size,
            allow_tera=payload.allow_tera,
        )
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/showdown/sessions/{session_id}/run-once")
async def run_showdown_session_once(
    session_id: str,
    payload: ShowdownSessionRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Receive one Showdown websocket payload, process it, and send generated commands."""
    try:
        result = await pokemon_showdown_session_service.run_once(
            session_id,
            auto_respond=payload.auto_respond,
            send_commands=payload.send_commands,
            team_size=payload.team_size,
            allow_tera=payload.allow_tera,
        )
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/showdown/sessions/{session_id}/run-until")
async def run_showdown_session_until(
    session_id: str,
    payload: ShowdownSessionRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run a Showdown websocket automation loop for a bounded number of messages."""
    try:
        result = await pokemon_showdown_session_service.run_until(
            session_id,
            max_messages=payload.max_messages,
            stop_on_finished=payload.stop_on_finished,
            auto_respond=payload.auto_respond,
            send_commands=payload.send_commands,
            team_size=payload.team_size,
            allow_tera=payload.allow_tera,
            stop_on_error=payload.stop_on_error,
        )
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/showdown/sessions/{session_id}/autopilot")
async def autopilot_showdown_session(
    session_id: str,
    payload: ShowdownSessionAutopilotRequest,
    db: AsyncSession = Depends(get_db),
):
    """Connect, optionally search, and run a bounded autonomous Showdown loop."""
    try:
        result = await pokemon_showdown_session_service.autopilot(
            session_id,
            max_messages=payload.max_messages,
            stop_on_finished=payload.stop_on_finished,
            auto_respond=payload.auto_respond,
            send_commands=payload.send_commands,
            team_size=payload.team_size,
            allow_tera=payload.allow_tera,
            auto_search=payload.auto_search,
            close_on_finish=payload.close_on_finish,
            stop_on_error=payload.stop_on_error,
        )
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/showdown/sessions/{session_id}/close")
async def close_showdown_session(session_id: str):
    """Close a connected Pokemon Showdown websocket session."""
    try:
        return await pokemon_showdown_session_service.close_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/showdown/sessions/{session_id}")
async def delete_showdown_session(session_id: str):
    """Delete an in-memory Pokemon Showdown automation session."""
    deleted = pokemon_showdown_session_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Pokemon Showdown session not found")
    return {"deleted": True}


def _required(value: str | None, name: str) -> str:
    if value is None or value == "":
        raise ValueError(f"{name} is required.")
    return value


def _raise_missing(name: str):
    raise ValueError(f"{name} is required.")


async def _persist_showdown_learning(db: AsyncSession, result: dict) -> dict:
    session = result.get("session") or {}
    analysis = session.get("analysis") or {}
    if not session:
        return {}
    profile = await pokemon_showdown_learning_store.record_session(
        db,
        session_id=session.get("session_id", ""),
        username=session.get("username", ""),
        battle_format=session.get("battle_format", "vgc2024"),
        showdown_format=session.get("showdown_format", session.get("battle_format", "vgc2024")),
        mode=session.get("mode", "balanced"),
        analysis=analysis,
        decisions=session.get("decisions") or [],
    )
    state = pokemon_showdown_session_service.get_session(session.get("session_id", ""))
    if state is not None and profile:
        state.learning_profile = profile
        result["session"] = state.to_dict()
    return profile


async def _resolve_showdown_mode(
    db: AsyncSession,
    *,
    username: str,
    battle_format: str,
    requested_mode: str,
) -> tuple[str, str, dict, dict]:
    allowed_modes = {"balanced", "aggressive", "defensive"}
    format_info = pokemon_format_catalog.get(battle_format)
    profile = await pokemon_showdown_learning_store.profile(db, username=username, battle_format=format_info.id)
    if requested_mode in allowed_modes:
        return requested_mode, "manual", {}, profile
    if requested_mode != "auto":
        raise ValueError(f"Unsupported Showdown mode: {requested_mode}")

    recommendation = profile.get("recommendation") or {}
    recommended_mode = recommendation.get("mode")
    if recommended_mode not in allowed_modes:
        recommended_mode = "balanced"
        recommendation = {
            "mode": recommended_mode,
            "reason": "No reliable learned mode was available, so balanced was selected.",
        }
    return recommended_mode, "learning_profile", recommendation, profile


# Data loading endpoint
@router.post("/init-data")
async def initialize_pokemon_data(db: AsyncSession = Depends(get_db)):
    """Initialize Pokemon data from JSON files"""
    loader = PokemonDataLoader(db)
    counts = await loader.load_all()
    return {"loaded": counts}
