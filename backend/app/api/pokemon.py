"""
Pokemon Battle API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any, List
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
    ShowdownSessionMissionRequest,
    ShowdownSessionNextActionRequest,
    ShowdownSessionRunRequest,
    ShowdownSessionSupervisorRequest,
    ShowdownTrainingChainRequest,
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
from app.services.pokemon.showdown_team_factory import pokemon_showdown_team_factory

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
                battle_format=payload.battle_format,
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
                battle_format=payload.battle_format,
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
    session = await _create_showdown_session_state(payload, db)
    return session.to_dict()


@router.post("/showdown/mission/plan")
async def plan_showdown_mission(payload: ShowdownSessionMissionRequest, db: AsyncSession = Depends(get_db)):
    """Plan the next autonomous Showdown mission without creating a live session."""
    if payload.max_actions < 1 or payload.max_actions > 20:
        raise HTTPException(status_code=400, detail="max_actions must be between 1 and 20.")
    try:
        _normalize_showdown_mission_goal(payload.mission_goal)
        resolved_mode, mode_source, mode_recommendation, learning_profile = await _resolve_showdown_mode(
            db,
            username=payload.username,
            battle_format=payload.battle_format,
            requested_mode=payload.mode,
        )
        format_info = pokemon_format_catalog.get(payload.battle_format)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "Unsupported Pokemon battle format" in str(exc) else 400, detail=str(exc)) from exc

    snapshot = _build_showdown_mission_plan_snapshot(
        payload,
        format_info=format_info,
        resolved_mode=resolved_mode,
        mode_source=mode_source,
        mode_recommendation=mode_recommendation,
        learning_profile=learning_profile,
    )
    mission_policy = _resolve_showdown_mission_policy(payload, snapshot)
    mission_request = {
        "username": payload.username,
        "battle_format": format_info.id,
        "mode": payload.mode,
        "auto_login": payload.auto_login,
        "auto_accept_challenges": payload.auto_accept_challenges,
        "auto_research_team": payload.auto_research_team,
        "mission_goal": payload.mission_goal,
        "auto_search": mission_policy["auto_search"],
        "require_live_readiness": mission_policy["require_live_readiness"],
        "max_actions": payload.max_actions,
        "max_messages": payload.max_messages,
        "send_commands": payload.send_commands,
        "stop_on_finished": payload.stop_on_finished,
        "stop_on_error": payload.stop_on_error,
        "stop_on_new_session": mission_policy["stop_on_new_session"],
        "max_results": payload.max_results,
    }
    return {
        "username": payload.username,
        "battle_format": format_info.id,
        "showdown_format": format_info.showdown_format,
        "mode": resolved_mode,
        "requested_mode": payload.mode,
        "mode_source": mode_source,
        "mode_recommendation": mode_recommendation,
        "learning_profile": learning_profile,
        "training_plan": learning_profile.get("training_plan"),
        "team_source": snapshot.get("team_source"),
        "team_reason": snapshot.get("team_reason"),
        "team_species": snapshot.get("team_species"),
        "team_adjustments": snapshot.get("team_adjustments"),
        "team_audit": mission_policy["team_audit"],
        "team_audit_actions": mission_policy["team_audit_actions"],
        "team_audit_gaps": mission_policy["team_audit_gaps"],
        "live_readiness": mission_policy["live_readiness"],
        "readiness_status": mission_policy["readiness_status"],
        "readiness_score": mission_policy["readiness_score"],
        "readiness_actions": mission_policy["readiness_actions"],
        "require_live_readiness": mission_policy["require_live_readiness"],
        "mission_goal": mission_policy["mission_goal"],
        "requested_mission_goal": mission_policy["requested_mission_goal"],
        "mission_goal_source": mission_policy["mission_goal_source"],
        "mission_goal_reason": mission_policy["mission_goal_reason"],
        "allowed_actions": mission_policy["allowed_actions"],
        "training_plan_actions": mission_policy["training_plan_actions"],
        "training_task_actions": mission_policy["training_task_actions"],
        "policy_evaluation": mission_policy["policy_evaluation"],
        "policy_actions": mission_policy["policy_actions"],
        "executable_plan_actions": mission_policy["executable_plan_actions"],
        "executable_task_actions": mission_policy["executable_task_actions"],
        "executable_policy_actions": mission_policy["executable_policy_actions"],
        "unsupported_plan_actions": mission_policy["unsupported_plan_actions"],
        "unsupported_task_actions": mission_policy["unsupported_task_actions"],
        "unsupported_policy_actions": mission_policy["unsupported_policy_actions"],
        "training_tasks": mission_policy["training_tasks"],
        "action_plan_source": mission_policy["action_plan_source"],
        "mission_request": mission_request,
    }


@router.post("/showdown/mission")
async def start_showdown_mission(payload: ShowdownSessionMissionRequest, db: AsyncSession = Depends(get_db)):
    """Create a Showdown session and immediately run a bounded autonomous supervisor."""
    if payload.max_actions < 1 or payload.max_actions > 20:
        raise HTTPException(status_code=400, detail="max_actions must be between 1 and 20.")
    try:
        _normalize_showdown_mission_goal(payload.mission_goal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = await _create_showdown_session_state(payload, db, max_results=payload.max_results)
    mission_policy = _resolve_showdown_mission_policy(payload, session.to_dict())
    supervisor_payload = ShowdownSessionSupervisorRequest(
        action=payload.start_action,
        max_messages=payload.max_messages,
        auto_search=mission_policy["auto_search"],
        send_commands=payload.send_commands,
        stop_on_finished=payload.stop_on_finished,
        stop_on_error=payload.stop_on_error,
        max_results=payload.max_results,
        max_actions=payload.max_actions,
        allowed_actions=mission_policy["allowed_actions"],
        stop_actions=mission_policy["stop_actions"],
        stop_on_new_session=mission_policy["stop_on_new_session"],
        require_live_readiness=mission_policy["require_live_readiness"],
    )
    supervisor = await supervise_showdown_session(session.session_id, supervisor_payload, db)
    final_session = supervisor.get("session") or session.to_dict()
    training_task_progress = _build_showdown_training_task_progress(
        mission_policy["training_tasks"],
        supervisor.get("steps") or [],
        stop_reason=supervisor.get("stop_reason"),
    )
    policy_progress = _build_showdown_policy_action_progress(
        mission_policy["policy_actions"],
        supervisor.get("steps") or [],
        stop_reason=supervisor.get("stop_reason"),
    )
    mission_summary = {
        "session_id": supervisor.get("session_id", session.session_id),
        "original_session_id": session.session_id,
        "username": payload.username,
        "battle_format": final_session.get("battle_format"),
        "showdown_format": final_session.get("showdown_format"),
        "team_source": final_session.get("team_source"),
        "mode": final_session.get("mode"),
        "requested_mission_goal": mission_policy["requested_mission_goal"],
        "mission_goal": mission_policy["mission_goal"],
        "mission_goal_source": mission_policy["mission_goal_source"],
        "mission_goal_reason": mission_policy["mission_goal_reason"],
        "allowed_actions": mission_policy["allowed_actions"],
        "training_plan_actions": mission_policy["training_plan_actions"],
        "training_task_actions": mission_policy["training_task_actions"],
        "policy_evaluation": mission_policy["policy_evaluation"],
        "policy_actions": mission_policy["policy_actions"],
        "executable_plan_actions": mission_policy["executable_plan_actions"],
        "executable_task_actions": mission_policy["executable_task_actions"],
        "executable_policy_actions": mission_policy["executable_policy_actions"],
        "unsupported_plan_actions": mission_policy["unsupported_plan_actions"],
        "unsupported_task_actions": mission_policy["unsupported_task_actions"],
        "unsupported_policy_actions": mission_policy["unsupported_policy_actions"],
        "training_tasks": mission_policy["training_tasks"],
        "training_task_progress": training_task_progress,
        "training_task_status": training_task_progress["status"],
        "training_task_completed_count": training_task_progress["completed_count"],
        "training_task_pending_count": training_task_progress["pending_count"],
        "training_task_partial_count": training_task_progress["partial_count"],
        "training_task_unsupported_count": training_task_progress["unsupported_count"],
        "policy_progress": policy_progress,
        "policy_status": policy_progress["status"],
        "policy_completed_count": policy_progress["completed_count"],
        "policy_pending_count": policy_progress["pending_count"],
        "policy_partial_count": policy_progress["partial_count"],
        "policy_unsupported_count": policy_progress["unsupported_count"],
        "action_plan_source": mission_policy["action_plan_source"],
        "team_audit": final_session.get("team_audit") or mission_policy["team_audit"],
        "team_audit_actions": mission_policy["team_audit_actions"],
        "team_audit_gaps": mission_policy["team_audit_gaps"],
        "live_readiness": final_session.get("live_readiness") or mission_policy["live_readiness"],
        "readiness_status": mission_policy["readiness_status"],
        "readiness_score": mission_policy["readiness_score"],
        "readiness_actions": mission_policy["readiness_actions"],
        "require_live_readiness": mission_policy["require_live_readiness"],
        "stop_reason": supervisor.get("stop_reason"),
        "step_count": supervisor.get("step_count", 0),
        "training_plan": (final_session.get("learning_profile") or {}).get("training_plan"),
    }
    stored_mission = pokemon_showdown_session_service.store_mission_summary(
        mission_summary["session_id"],
        mission_summary,
    )
    final_state = pokemon_showdown_session_service.get_session(mission_summary["session_id"])
    final_session = final_state.to_dict() if final_state else final_session
    return {
        "session": final_session,
        "supervisor": supervisor,
        "mission_summary": stored_mission,
    }


@router.post("/showdown/training-chain")
async def run_showdown_training_chain(payload: ShowdownTrainingChainRequest, db: AsyncSession = Depends(get_db)):
    """Plan and execute multiple adaptive Showdown missions as one bounded training chain."""
    if payload.rounds < 1 or payload.rounds > 10:
        raise HTTPException(status_code=400, detail="rounds must be between 1 and 10.")
    if payload.max_actions < 1 or payload.max_actions > 20:
        raise HTTPException(status_code=400, detail="max_actions must be between 1 and 20.")
    if payload.mastery_score_target is not None and payload.mastery_score_target < 0:
        raise HTTPException(status_code=400, detail="mastery_score_target must be greater than or equal to 0.")

    try:
        format_info = pokemon_format_catalog.get(payload.battle_format)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    baseline_learning_profile = await pokemon_showdown_learning_store.profile(
        db,
        username=payload.username,
        battle_format=format_info.id,
    )
    baseline_mastery_score = pokemon_showdown_learning_store.score_profile(baseline_learning_profile)

    mission_payload = ShowdownSessionMissionRequest(
        **payload.model_dump(exclude={"rounds", "resume_recovery", "mastery_score_target", "stop_on_no_progress"})
    )
    rounds = []
    stop_reason = "round_limit"
    final_session = None
    latest_learning_profile = None
    latest_mastery_score = None
    previous_recovery = _find_showdown_training_chain_resume_recovery(
        username=payload.username,
        battle_format=format_info.id,
    ) if payload.resume_recovery else None
    initial_recovery = previous_recovery
    recovery_source = "previous_training_chain_recovery" if previous_recovery else "previous_round_recovery"

    for index in range(payload.rounds):
        recovery_action_source = _build_showdown_recovery_action_source(
            previous_recovery,
            custom_allowed_actions=payload.allowed_actions,
            source=recovery_source,
        )
        current_mission_payload = mission_payload
        if recovery_action_source["actions"]:
            current_mission_payload = mission_payload.model_copy(
                update={"allowed_actions": recovery_action_source["actions"]}
            )
        plan = await plan_showdown_mission(current_mission_payload, db)
        mission = await start_showdown_mission(current_mission_payload, db)
        final_session = mission.get("session")
        supervisor = mission.get("supervisor") or {}
        mission_summary = mission.get("mission_summary") or {}
        learning_profile = (
            supervisor.get("learning_profile")
            or (final_session or {}).get("learning_profile")
            or await pokemon_showdown_learning_store.profile(
                db,
                username=payload.username,
                battle_format=plan["battle_format"],
            )
        )
        latest_learning_profile = learning_profile
        latest_mastery_score = pokemon_showdown_learning_store.score_profile(learning_profile)
        round_summary = {
            "round": index + 1,
            "planned_goal": plan["mission_goal"],
            "planned_goal_source": plan["mission_goal_source"],
            "planned_actions": plan["allowed_actions"],
            "action_plan_source": plan["action_plan_source"],
            "recovery_action_source": recovery_action_source,
            "session_id": (final_session or {}).get("session_id"),
            "status": (final_session or {}).get("status"),
            "mission_summary": mission_summary,
            "supervisor_stop_reason": supervisor.get("stop_reason"),
            "supervisor_step_count": supervisor.get("step_count", 0),
            "learning_profile": learning_profile,
            "mastery_score": latest_mastery_score,
        }
        round_summary["recovery"] = _build_showdown_round_recovery(round_summary)
        round_summary["recovery_effectiveness"] = _build_showdown_recovery_effectiveness(
            round_summary["recovery_action_source"],
            round_summary["recovery"],
        )
        rounds.append(round_summary)
        previous_recovery = round_summary["recovery"]
        recovery_source = "previous_round_recovery"

        if payload.mastery_score_target is not None and latest_mastery_score >= payload.mastery_score_target:
            stop_reason = "mastery_score_target"
            break
        if payload.stop_on_error and supervisor.get("stop_reason") == "error":
            stop_reason = "error"
            break
        if payload.stop_on_no_progress and int(supervisor.get("step_count") or 0) == 0:
            stop_reason = "no_progress"
            break
    else:
        stop_reason = "round_limit"

    progress = _build_showdown_training_chain_progress(
        baseline_learning_profile=baseline_learning_profile,
        baseline_mastery_score=baseline_mastery_score,
        latest_learning_profile=latest_learning_profile,
        latest_mastery_score=latest_mastery_score,
    )
    recovery = _build_showdown_training_chain_recovery(rounds)
    recovery_effectiveness = _build_showdown_training_chain_recovery_effectiveness(rounds)
    training_chain_summary = None
    if final_session and final_session.get("session_id"):
        training_chain_summary = pokemon_showdown_session_service.store_training_chain_summary(
            final_session["session_id"],
            {
                "username": payload.username,
                "battle_format": final_session.get("battle_format"),
                "showdown_format": final_session.get("showdown_format"),
                "requested_rounds": payload.rounds,
                "completed_rounds": len(rounds),
                "stop_reason": stop_reason,
                "mastery_score": latest_mastery_score,
                "learning_battles": (latest_learning_profile or {}).get("battles", 0),
                "progress": progress,
                "initial_recovery": initial_recovery,
                "recovery": recovery,
                "recovery_effectiveness": recovery_effectiveness,
                "last_goal": rounds[-1]["planned_goal"] if rounds else None,
                "last_goal_source": rounds[-1]["planned_goal_source"] if rounds else None,
                "rounds": [
                    {
                        "round": item["round"],
                        "planned_goal": item["planned_goal"],
                        "planned_goal_source": item["planned_goal_source"],
                        "recovery_action_source": item["recovery_action_source"],
                        "supervisor_stop_reason": item["supervisor_stop_reason"],
                        "supervisor_step_count": item["supervisor_step_count"],
                        "recovery_status": item["recovery"]["status"],
                        "recovery_actions": item["recovery"]["actions"],
                        "recovery_effectiveness": item["recovery_effectiveness"],
                        "mastery_score": item["mastery_score"],
                    }
                    for item in rounds
                ],
            },
        )
        refreshed = pokemon_showdown_session_service.get_session(final_session["session_id"])
        final_session = refreshed.to_dict() if refreshed else final_session

    return {
        "username": payload.username,
        "battle_format": (rounds[-1]["mission_summary"].get("battle_format") if rounds else payload.battle_format),
        "requested_rounds": payload.rounds,
        "completed_rounds": len(rounds),
        "stop_reason": stop_reason,
        "final_session": final_session,
        "learning_profile": latest_learning_profile,
        "mastery_score": latest_mastery_score,
        "progress": progress,
        "initial_recovery": initial_recovery,
        "recovery": recovery,
        "recovery_effectiveness": recovery_effectiveness,
        "training_chain_summary": training_chain_summary,
        "rounds": rounds,
    }


async def _create_showdown_session_state(
    payload: ShowdownSessionCreateRequest,
    db: AsyncSession,
    *,
    max_results: int = 3,
):
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
            max_results=max_results,
        )
        session = pokemon_showdown_session_service.attach_knowledge_context(session.session_id, context)
    return session


def _build_showdown_training_chain_progress(
    *,
    baseline_learning_profile: dict | None,
    baseline_mastery_score: float | None,
    latest_learning_profile: dict | None,
    latest_mastery_score: float | None,
) -> dict:
    before_score = float(baseline_mastery_score) if baseline_mastery_score is not None else 0.0
    after_score = float(latest_mastery_score) if latest_mastery_score is not None else before_score
    before_battles = int((baseline_learning_profile or {}).get("battles") or 0)
    after_battles = int((latest_learning_profile or baseline_learning_profile or {}).get("battles") or before_battles)
    score_delta = round(after_score - before_score, 2)
    battle_delta = max(0, after_battles - before_battles)
    if score_delta > 0:
        direction = "improved"
        recommendation = "Continue the current training chain while the mastery score is rising."
    elif score_delta < 0:
        direction = "declined"
        recommendation = "Review the losing or low-reward samples before extending the training chain."
    elif battle_delta > 0:
        direction = "sampled"
        recommendation = "Review the new samples before extending the training chain."
    else:
        direction = "unchanged"
        recommendation = "No new completed battle sample was recorded; run or resume live Showdown battles."
    return {
        "before_mastery_score": round(before_score, 2),
        "after_mastery_score": round(after_score, 2),
        "mastery_score_delta": score_delta,
        "before_battles": before_battles,
        "after_battles": after_battles,
        "battle_delta": battle_delta,
        "direction": direction,
        "improved": score_delta > 0,
        "recommendation": recommendation,
    }


def _build_showdown_recovery_action_source(
    previous_recovery: dict[str, Any] | None,
    *,
    custom_allowed_actions: list[str] | None,
    source: str = "previous_round_recovery",
) -> dict[str, Any]:
    if custom_allowed_actions:
        return {
            "status": "custom_override",
            "source": "custom_allowed_actions",
            "actions": [],
            "reason": "Custom allowed_actions were provided, so recovery actions were not injected.",
        }
    if not previous_recovery:
        return {
            "status": "none",
            "source": "first_round",
            "actions": [],
            "reason": "No previous training round is available.",
        }

    actions = [str(action) for action in previous_recovery.get("actions") or [] if str(action)]
    if previous_recovery.get("status") != "resume" or not actions:
        return {
            "status": str(previous_recovery.get("status") or "clear"),
            "source": source,
            "actions": [],
            "reason": "Previous recovery state did not expose executable resume actions.",
        }

    return {
        "status": "applied",
        "source": source,
        "actions": list(dict.fromkeys(actions)),
        "reason": "Previous incomplete training tasks were promoted to this round's action allow-list.",
    }


def _find_showdown_training_chain_resume_recovery(username: str, battle_format: str) -> dict[str, Any] | None:
    normalized_username = str(username or "").lower()
    normalized_format = str(battle_format or "").lower()
    for session in pokemon_showdown_session_service.list_sessions():
        snapshot = session.to_dict()
        if str(snapshot.get("username") or "").lower() != normalized_username:
            continue
        if str(snapshot.get("battle_format") or "").lower() != normalized_format:
            continue
        summary = snapshot.get("last_training_chain_summary") or {}
        recovery = summary.get("recovery") if isinstance(summary, dict) else None
        if not isinstance(recovery, dict):
            continue
        actions = [str(action) for action in recovery.get("actions") or [] if str(action)]
        if recovery.get("status") != "resume" or not actions:
            continue
        seeded = dict(recovery)
        seeded["actions"] = actions
        seeded["chain_number"] = summary.get("chain_number")
        seeded["session_id"] = snapshot.get("session_id")
        return seeded
    return None


def _build_showdown_round_recovery(round_summary: dict[str, Any]) -> dict[str, Any]:
    mission_summary = round_summary.get("mission_summary") or {}
    recovery_sources = [
        ("training_task", (mission_summary.get("training_task_progress") or {}).get("tasks") or []),
        ("policy", (mission_summary.get("policy_progress") or {}).get("tasks") or []),
    ]
    action_counts: dict[str, int] = {}
    task_recovery: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []

    for source, task_items in recovery_sources:
        for task in task_items:
            if not isinstance(task, dict):
                continue
            status = str(task.get("status") or "")
            if status not in {"pending", "partial", "unsupported"}:
                continue
            missing_actions = [str(action) for action in task.get("missing_actions") or [] if str(action)]
            unsupported_actions = [str(action) for action in task.get("unsupported_actions") or [] if str(action)]
            for action in missing_actions:
                action_counts[action] = action_counts.get(action, 0) + 1
            blocked_reason = str(task.get("blocked_reason") or "")
            if blocked_reason and blocked_reason not in blocked_reasons:
                blocked_reasons.append(blocked_reason)
            task_recovery.append(
                {
                    "id": task.get("id"),
                    "source": source,
                    "action": task.get("action"),
                    "status": status,
                    "priority": task.get("priority"),
                    "missing_actions": missing_actions,
                    "unsupported_actions": unsupported_actions,
                    "blocked_reason": blocked_reason,
                }
            )

    if not task_recovery:
        return {
            "status": "clear",
            "actions": [],
            "action_counts": {},
            "task_count": 0,
            "policy_count": 0,
            "tasks": [],
            "blocked_reasons": [],
            "recommendation": "No recovery action is needed from this round.",
        }

    actions = sorted(action_counts, key=lambda action: (-action_counts[action], action))
    unsupported_count = sum(1 for task in task_recovery if task["status"] == "unsupported")
    policy_count = sum(1 for task in task_recovery if task.get("source") == "policy")
    task_count = len(task_recovery) - policy_count
    if unsupported_count == len(task_recovery):
        status = "unsupported"
        recommendation = "Add supported mappings for unsupported training or policy actions before the next chain."
    elif actions:
        status = "resume"
        recommendation = f"Resume the next chain with {', '.join(actions[:4])} before broadening the mission."
    else:
        status = "blocked"
        recommendation = "Review blocked training tasks before extending the chain."

    return {
        "status": status,
        "actions": actions,
        "action_counts": action_counts,
        "task_count": task_count,
        "policy_count": policy_count,
        "tasks": task_recovery,
        "blocked_reasons": blocked_reasons,
        "recommendation": recommendation,
    }


def _build_showdown_training_chain_recovery(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts: dict[str, int] = {}
    blocked_reasons: list[str] = []
    round_recovery: list[dict[str, Any]] = []
    task_count = 0
    policy_count = 0

    for round_item in rounds:
        recovery = round_item.get("recovery") or _build_showdown_round_recovery(round_item)
        for action, count in (recovery.get("action_counts") or {}).items():
            action_counts[str(action)] = action_counts.get(str(action), 0) + int(count or 0)
        for reason in recovery.get("blocked_reasons") or []:
            reason_text = str(reason)
            if reason_text and reason_text not in blocked_reasons:
                blocked_reasons.append(reason_text)
        task_count += int(recovery.get("task_count") or 0)
        policy_count += int(recovery.get("policy_count") or 0)
        if recovery.get("status") != "clear":
            round_recovery.append(
                {
                    "round": round_item.get("round"),
                    "status": recovery.get("status"),
                    "actions": recovery.get("actions") or [],
                    "task_count": recovery.get("task_count") or 0,
                    "policy_count": recovery.get("policy_count") or 0,
                }
            )

    actions = sorted(action_counts, key=lambda action: (-action_counts[action], action))
    if not rounds:
        status = "none"
        recommendation = "No training rounds were executed."
    elif not round_recovery:
        status = "clear"
        recommendation = "All mapped training task actions completed across the chain."
    elif actions:
        status = "resume"
        recommendation = f"Start the next chain with recovery actions: {', '.join(actions[:5])}."
    else:
        status = "blocked"
        recommendation = "Review unsupported or blocked training tasks before the next chain."

    return {
        "status": status,
        "actions": actions,
        "action_counts": action_counts,
        "task_count": task_count,
        "policy_count": policy_count,
        "rounds": round_recovery,
        "blocked_reasons": blocked_reasons,
        "recommendation": recommendation,
    }


def _build_showdown_recovery_effectiveness(
    recovery_action_source: dict[str, Any] | None,
    recovery: dict[str, Any] | None,
) -> dict[str, Any]:
    source = recovery_action_source or {}
    recovery = recovery or {}
    applied_actions = list(dict.fromkeys(str(action) for action in source.get("actions") or [] if str(action)))
    remaining_actions = list(dict.fromkeys(str(action) for action in recovery.get("actions") or [] if str(action)))
    remaining_set = set(remaining_actions)
    recovered_actions = [action for action in applied_actions if action not in remaining_set]
    still_pending_actions = [action for action in applied_actions if action in remaining_set]
    new_actions = [action for action in remaining_actions if action not in set(applied_actions)]

    if not applied_actions:
        status = "not_applied"
        recommendation = "No recovery actions were injected into this round."
    elif not still_pending_actions and not new_actions:
        status = "cleared"
        recommendation = "Injected recovery actions cleared the pending queue."
    elif recovered_actions and still_pending_actions:
        status = "partial"
        recommendation = "Some recovery actions cleared, but the next round should continue the still-pending actions."
    elif recovered_actions and new_actions:
        status = "shifted"
        recommendation = "Injected recovery actions cleared, but new recovery actions appeared and should seed the next round."
    else:
        status = "stuck"
        recommendation = "Injected recovery actions are still pending; broaden the next round or inspect blocked supervisor steps."

    applied_count = len(applied_actions)
    recovered_count = len(recovered_actions)
    burndown_ratio = round(recovered_count / applied_count, 2) if applied_count else 0.0
    return {
        "status": status,
        "source": source.get("source") or "none",
        "applied_actions": applied_actions,
        "remaining_actions": remaining_actions,
        "recovered_actions": recovered_actions,
        "still_pending_actions": still_pending_actions,
        "new_actions": new_actions,
        "applied_count": applied_count,
        "recovered_count": recovered_count,
        "still_pending_count": len(still_pending_actions),
        "new_count": len(new_actions),
        "remaining_count": len(remaining_actions),
        "burndown_ratio": burndown_ratio,
        "recommendation": recommendation,
    }


def _build_showdown_training_chain_recovery_effectiveness(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    round_effects = [
        round_item.get("recovery_effectiveness")
        or _build_showdown_recovery_effectiveness(
            round_item.get("recovery_action_source"),
            round_item.get("recovery"),
        )
        for round_item in rounds
    ]
    applied_rounds = [effect for effect in round_effects if int(effect.get("applied_count") or 0) > 0]
    action_counts = {
        "applied": {},
        "recovered": {},
        "still_pending": {},
        "new": {},
    }
    for effect in applied_rounds:
        for bucket, key in (
            ("applied", "applied_actions"),
            ("recovered", "recovered_actions"),
            ("still_pending", "still_pending_actions"),
            ("new", "new_actions"),
        ):
            for action in effect.get(key) or []:
                action_text = str(action)
                action_counts[bucket][action_text] = action_counts[bucket].get(action_text, 0) + 1

    applied_count = sum(int(effect.get("applied_count") or 0) for effect in applied_rounds)
    recovered_count = sum(int(effect.get("recovered_count") or 0) for effect in applied_rounds)
    still_pending_count = sum(int(effect.get("still_pending_count") or 0) for effect in applied_rounds)
    new_count = sum(int(effect.get("new_count") or 0) for effect in applied_rounds)
    stuck_rounds = sum(1 for effect in applied_rounds if effect.get("status") == "stuck")
    partial_rounds = sum(1 for effect in applied_rounds if effect.get("status") in {"partial", "shifted"})
    cleared_rounds = sum(1 for effect in applied_rounds if effect.get("status") == "cleared")

    if not applied_rounds:
        status = "none"
        recommendation = "No recovery actions were injected during this chain."
    elif still_pending_count == 0 and new_count == 0:
        status = "cleared"
        recommendation = "Recovery injections cleared all pending recovery actions."
    elif recovered_count and still_pending_count:
        status = "partial"
        recommendation = "Recovery is burning down, but the next chain should continue still-pending actions first."
    elif stuck_rounds:
        status = "stuck"
        recommendation = "Recovery actions repeated without clearing; broaden allowed actions or inspect supervisor blockers."
    else:
        status = "shifted"
        recommendation = "Previous recovery actions cleared, but new recovery work appeared."

    burndown_ratio = round(recovered_count / applied_count, 2) if applied_count else 0.0
    return {
        "status": status,
        "applied_rounds": len(applied_rounds),
        "cleared_rounds": cleared_rounds,
        "partial_rounds": partial_rounds,
        "stuck_rounds": stuck_rounds,
        "applied_count": applied_count,
        "recovered_count": recovered_count,
        "still_pending_count": still_pending_count,
        "new_count": new_count,
        "burndown_ratio": burndown_ratio,
        "action_counts": action_counts,
        "applied_actions": sorted(action_counts["applied"], key=lambda action: (-action_counts["applied"][action], action)),
        "recovered_actions": sorted(action_counts["recovered"], key=lambda action: (-action_counts["recovered"][action], action)),
        "still_pending_actions": sorted(
            action_counts["still_pending"],
            key=lambda action: (-action_counts["still_pending"][action], action),
        ),
        "new_actions": sorted(action_counts["new"], key=lambda action: (-action_counts["new"][action], action)),
        "rounds": [
            {
                "round": round_item.get("round"),
                "status": effect.get("status"),
                "applied_count": effect.get("applied_count") or 0,
                "recovered_count": effect.get("recovered_count") or 0,
                "still_pending_count": effect.get("still_pending_count") or 0,
                "new_count": effect.get("new_count") or 0,
            }
            for round_item, effect in zip(rounds, round_effects)
        ],
        "recommendation": recommendation,
    }


def _build_showdown_format_capability(format_info, learning_profile: dict | None = None) -> dict:
    team_source = "not_required"
    team_reason = f"{format_info.name} supplies teams on Pokemon Showdown."
    generated_species: list[str] = []
    team_audit: dict[str, Any] = {}
    can_build_team = True
    if format_info.requires_team:
        generated = pokemon_showdown_team_factory.generate(
            format_info.id,
            mode=(learning_profile or {}).get("recommended_mode") or "balanced",
            learning_profile=learning_profile,
        )
        can_build_team = generated is not None
        team_source = generated.source if generated else "unavailable"
        team_reason = generated.reason if generated else f"No autonomous team builder is available for {format_info.name}."
        generated_species = generated.species() if generated else []
        team_audit = generated.audit if generated else {}

    learning_profile = learning_profile or {}
    battles = int(learning_profile.get("battles") or 0)
    training_plan = learning_profile.get("training_plan") or {}
    blockers: list[str] = []
    if format_info.requires_team and not can_build_team:
        blockers.append("team_builder")
    if format_info.active_pokemon not in {1, 2}:
        blockers.append("target_policy")

    action_items: list[str] = []
    if blockers:
        action_items.append("prepare_format_support")
    if battles == 0:
        action_items.append("collect_samples")
    if format_info.requires_team and can_build_team and generated_species:
        action_items.append("research_team")
    action_items.append(training_plan.get("next_mission_goal") or "ladder")

    readiness = "blocked" if blockers else "ready"
    strategy_profile = format_info.strategy_profile()
    target_policy = strategy_profile["target_policy"]
    return {
        "format": format_info.to_dict(),
        "automation_readiness": readiness,
        "blockers": blockers,
        "strategy_profile": strategy_profile,
        "team": {
            "requires_team": format_info.requires_team,
            "can_build": can_build_team,
            "source": team_source,
            "reason": team_reason,
            "species": generated_species,
            "audit": team_audit,
        },
        "battle_policy": {
            "battle_type": format_info.battle_type,
            "active_pokemon": format_info.active_pokemon,
            "team_size": format_info.team_size,
            "target_policy": target_policy,
            "archetype": strategy_profile["archetype"],
            "priorities": strategy_profile["priorities"],
            "risk_controls": strategy_profile["risk_controls"],
            "supports_team_preview": format_info.requires_team,
            "supports_autopilot": not blockers,
        },
        "learning": {
            "battles": battles,
            "wins": int(learning_profile.get("wins") or 0),
            "win_rate": float(learning_profile.get("win_rate") or 0.0),
            "mastery_score": pokemon_showdown_learning_store.score_profile(learning_profile) if learning_profile else 0.0,
            "training_stage": training_plan.get("stage") or "collect_data",
            "next_mission_goal": training_plan.get("next_mission_goal") or "queue",
            "recommended_mode": learning_profile.get("recommended_mode") or training_plan.get("recommended_mode") or "balanced",
        },
        "recommended_actions": list(dict.fromkeys(action_items)),
    }


async def _build_showdown_tactical_briefing(
    db: AsyncSession,
    *,
    username: str,
    battle_format: str,
    mode: str,
    include_knowledge: bool,
    max_results: int,
) -> dict:
    resolved_mode, mode_source, mode_recommendation, learning_profile = await _resolve_showdown_mode(
        db,
        username=username,
        battle_format=battle_format,
        requested_mode=mode,
    )
    format_info = pokemon_format_catalog.get(battle_format)
    capability = _build_showdown_format_capability(format_info, learning_profile)
    generated = None
    team_members: list[dict[str, Any]] = []
    team_species: list[str] = []
    team_adjustments: list[dict[str, Any]] = []
    team_audit: dict[str, Any] = {}
    if format_info.requires_team:
        generated = pokemon_showdown_team_factory.generate(
            format_info.id,
            mode=resolved_mode,
            learning_profile=learning_profile,
        )
        if generated:
            team_members = generated.team
            team_species = generated.species()
            team_adjustments = generated.adjustments
            team_audit = generated.audit
    else:
        team_species = []

    knowledge_context = None
    if include_knowledge and team_species:
        knowledge_context = await pokemon_knowledge_service.search_team(
            db,
            team_species,
            query_type="species_usage",
            max_results=max_results,
        )

    mission_recommendation = _recommend_showdown_mission_goal({
        "learning_profile": learning_profile,
        "has_knowledge_context": bool(knowledge_context),
        "team_species": team_species,
        "team_audit": team_audit,
    })
    training_plan = learning_profile.get("training_plan") or {}
    mastery_score = pokemon_showdown_learning_store.score_profile(learning_profile)
    tactical_plan = _build_showdown_tactical_plan(
        format_info=format_info,
        mode=resolved_mode,
        learning_profile=learning_profile,
        team_species=team_species,
        knowledge_context=knowledge_context,
        mission_recommendation=mission_recommendation,
    )

    return {
        "username": username,
        "battle_format": format_info.id,
        "showdown_format": format_info.showdown_format,
        "mode": resolved_mode,
        "requested_mode": mode,
        "mode_source": mode_source,
        "mode_recommendation": mode_recommendation,
        "format_capability": capability,
        "learning_profile": learning_profile,
        "mastery_score": mastery_score,
        "training_plan": training_plan,
        "mission_recommendation": mission_recommendation,
        "team": {
            "requires_team": format_info.requires_team,
            "source": generated.source if generated else capability["team"]["source"],
            "reason": generated.reason if generated else capability["team"]["reason"],
            "species": team_species,
            "adjustments": team_adjustments,
            "audit": team_audit if team_audit else capability["team"].get("audit", {}),
            "preview": [
                {
                    "slot": index + 1,
                    "species": str(member.get("species") or member.get("name") or "Unknown"),
                    "item": member.get("item"),
                    "ability": member.get("ability"),
                    "tera_type": member.get("tera_type"),
                    "moves": [str(move.get("name") if isinstance(move, dict) else move) for move in member.get("moves") or []],
                }
                for index, member in enumerate(team_members)
            ],
        },
        "knowledge_context": knowledge_context,
        "tactical_plan": tactical_plan,
        "next_session_request": {
            "username": username,
            "battle_format": format_info.id,
            "mode": mode,
            "auto_login": True,
            "auto_research_team": include_knowledge,
            "auto_search": mission_recommendation["mission_goal"] in {"queue", "ladder", "learn"},
            "mission_goal": mission_recommendation["mission_goal"],
            "max_actions": 5,
        },
    }


def _build_showdown_tactical_plan(
    *,
    format_info,
    mode: str,
    learning_profile: dict,
    team_species: list[str],
    knowledge_context: dict | None,
    mission_recommendation: dict,
) -> dict:
    battles = int(learning_profile.get("battles") or 0)
    win_rate = float(learning_profile.get("win_rate") or 0.0)
    average_reward = float(learning_profile.get("average_reward") or 0.0)
    faints_for = int(learning_profile.get("faints_for") or 0)
    faints_against = int(learning_profile.get("faints_against") or 0)
    needs_safety = battles == 0 or win_rate < 0.5 or average_reward < 50 or faints_against > faints_for
    battle_type = format_info.battle_type
    lead_count = min(format_info.active_pokemon, len(team_species)) if team_species else 0
    recommended_leads = team_species[:lead_count]
    bench_plan = team_species[lead_count:format_info.team_size] if team_species else []

    if battle_type == "double":
        opening = "Open with speed or Fake Out control, then protect vulnerable attackers while setting board position."
        target_policy = "Prioritize the opponent slot that threatens the fastest knockout or blocks speed control."
    else:
        opening = "Preserve defensive pivots early, remove hazards when possible, and keep the main cleaner healthy."
        target_policy = "No target selection is required; choose the highest-value move or switch for the active Pokemon."

    priorities = []
    if mode == "aggressive":
        priorities.append("take_fast_damage_trades")
    elif mode == "defensive":
        priorities.append("preserve_position")
    else:
        priorities.append("balance_damage_and_position")
    if needs_safety:
        priorities.extend(["avoid_free_knockouts", "favor_protect_or_switch_when_low_confidence"])
    else:
        priorities.extend(["push_advantage", "extend_successful_lines"])
    if knowledge_context and int(knowledge_context.get("result_count") or 0) > 0:
        priorities.append("use_web_usage_context")

    risk_controls = []
    if battles < 3:
        risk_controls.append("collect_baseline_samples_before_long_runs")
    if win_rate < 0.45 and battles:
        risk_controls.append("stop_after_loss_for_review")
    if faints_against > faints_for:
        risk_controls.append("reduce_high_risk_item_or_move_choices")
    if not knowledge_context and team_species:
        risk_controls.append("research_team_before_ladder")

    next_actions = []
    if team_species and not knowledge_context:
        next_actions.append("research_team")
    next_actions.append(mission_recommendation["mission_goal"])
    if mission_recommendation["mission_goal"] in {"queue", "ladder", "learn"}:
        next_actions.extend(["connect", "start_search", "autopilot"])

    return {
        "battle_type": battle_type,
        "opening_plan": opening,
        "target_policy": target_policy,
        "recommended_leads": recommended_leads,
        "bench_plan": bench_plan,
        "priorities": list(dict.fromkeys(priorities)),
        "risk_controls": list(dict.fromkeys(risk_controls)),
        "next_actions": list(dict.fromkeys(next_actions)),
        "confidence": "low" if battles < 3 else "medium" if needs_safety else "high",
        "reason": mission_recommendation["reason"],
    }


async def _build_showdown_matchup_briefing(
    db: AsyncSession,
    *,
    session: dict,
    room_id: str | None,
    include_knowledge: bool,
    max_results: int,
) -> dict:
    room = _select_showdown_matchup_room(session, room_id)
    if room is None:
        raise ValueError("No Showdown battle room with preview or battlefield data is available.")

    preview = room.get("preview") or {}
    agent_side = room.get("agent_side")
    opponent_side = room.get("opponent_side")
    if not opponent_side and agent_side:
        opponent_side = "p2" if agent_side == "p1" else "p1"
    if not agent_side:
        agent_side = _first_preview_side(preview)
    if not opponent_side:
        opponent_side = _first_preview_side(preview, exclude=agent_side)

    own_species = _unique_species(
        session.get("team_species")
        or [member.get("species") for member in session.get("team_preview") or []]
        or [member.get("species") for member in preview.get(agent_side or "") or []]
    )
    opponent_preview = list(preview.get(opponent_side or "") or [])
    opponent_species = _unique_species([member.get("species") for member in opponent_preview])
    battlefield = room.get("battlefield") or {}
    sides = battlefield.get("sides") or {}
    opponent_active = _battlefield_active_species(sides.get(opponent_side or "") or {})
    if opponent_active:
        opponent_species = _unique_species(opponent_active + opponent_species)

    knowledge_context = None
    if include_knowledge and opponent_species:
        knowledge_context = await pokemon_knowledge_service.search_team(
            db,
            opponent_species,
            query_type="matchup",
            max_results=max_results,
        )

    battle_type = session.get("battle_type") or "double"
    threats = _classify_showdown_matchup_threats(opponent_species, battle_type)
    plan = _build_showdown_matchup_plan(
        battle_type=battle_type,
        own_species=own_species,
        opponent_species=opponent_species,
        opponent_active=opponent_active,
        threats=threats,
        knowledge_context=knowledge_context,
    )

    return {
        "session_id": session.get("session_id"),
        "room_id": room.get("room_id"),
        "battle_format": session.get("battle_format"),
        "showdown_format": session.get("showdown_format"),
        "battle_type": battle_type,
        "sides": {
            "agent_side": agent_side,
            "opponent_side": opponent_side,
            "opponent_username": room.get("opponent_username"),
        },
        "team": {
            "species": own_species,
            "preview": session.get("team_preview") or [],
        },
        "opponent": {
            "species": opponent_species,
            "active": opponent_active,
            "preview": opponent_preview,
        },
        "knowledge_context": knowledge_context,
        "threats": threats,
        "matchup_plan": plan,
    }


def _select_showdown_matchup_room(session: dict, room_id: str | None) -> dict | None:
    rooms = session.get("room_details") or {}
    if room_id:
        room = rooms.get(room_id)
        if not room:
            raise ValueError(f"Showdown room not found: {room_id}")
        return room
    for room in rooms.values():
        if room.get("preview") or room.get("battlefield"):
            return room
    return None


def _first_preview_side(preview: dict, exclude: str | None = None) -> str | None:
    for side, members in preview.items():
        if side and side != exclude and members:
            return str(side)
    return None


def _unique_species(values: list[Any]) -> list[str]:
    species: list[str] = []
    seen = set()
    for value in values:
        name = str(value or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        species.append(name)
    return species


def _battlefield_active_species(side: dict) -> list[str]:
    active = side.get("active") or {}
    return _unique_species([
        slot.get("pokemon")
        for _, slot in sorted(active.items())
        if isinstance(slot, dict) and slot.get("pokemon")
    ])


def _classify_showdown_matchup_threats(opponent_species: list[str], battle_type: str) -> list[dict[str, str]]:
    threat_map = [
        ("speed_control", {"tornadus", "whimsicott", "pelipper", "talonflame", "farigiraf"}),
        ("fake_out", {"incineroar", "rillaboom", "iron hands", "hitmontop"}),
        ("redirection", {"amoonguss", "indeedee", "ogerpon-wellspring", "clefairy"}),
        ("spread_damage", {"flutter mane", "gholdengo", "landorus", "ursaluna-bloodmoon", "chi-yu"}),
        ("priority", {"rillaboom", "dragonite", "kingambit", "chien-pao"}),
        ("setup_sweeper", {"kingambit", "gholdengo", "dragonite", "gouging fire", "volcarona"}),
    ]
    threats: list[dict[str, str]] = []
    lower_species = {species.lower(): species for species in opponent_species}
    for threat_id, names in threat_map:
        matched = [display for key, display in lower_species.items() if key in names]
        if not matched:
            continue
        threats.append({
            "id": threat_id,
            "label": threat_id.replace("_", " ").title(),
            "species": ", ".join(matched),
            "priority": "high" if threat_id in {"speed_control", "fake_out", "spread_damage"} and battle_type == "double" else "normal",
        })
    if not threats and opponent_species:
        threats.append({
            "id": "unknown_core",
            "label": "Unknown Core",
            "species": ", ".join(opponent_species[:3]),
            "priority": "normal",
        })
    return threats


def _build_showdown_matchup_plan(
    *,
    battle_type: str,
    own_species: list[str],
    opponent_species: list[str],
    opponent_active: list[str],
    threats: list[dict[str, str]],
    knowledge_context: dict | None,
) -> dict:
    threat_ids = {threat["id"] for threat in threats}
    target_priority: list[str] = []
    lead_adjustments: list[str] = []
    risk_controls = ["respect_unknown_items_and_tera"]

    if battle_type == "double":
        if "speed_control" in threat_ids:
            target_priority.append("deny_or_match_speed_control")
            lead_adjustments.append("lead_fake_out_or_tailwind_answer")
        if "fake_out" in threat_ids:
            risk_controls.append("protect_key_attacker_from_fake_out_turn")
        if "redirection" in threat_ids:
            target_priority.append("remove_redirection_before_single_target_damage")
        if "spread_damage" in threat_ids:
            risk_controls.append("avoid_grouping_low_hp_pokemon_into_spread_damage")
        if opponent_active:
            target_priority.append(f"pressure_active_{opponent_active[0]}")
        opening_plan = "Use preview threats to choose a stable lead, protect the key attacker on uncertain turns, and target control pieces first."
    else:
        if "setup_sweeper" in threat_ids:
            target_priority.append("preserve_revenge_killer_for_setup_sweeper")
        if "priority" in threat_ids:
            risk_controls.append("avoid_leaving_cleaner_in_priority_range")
        opening_plan = "Scout the opponent core, keep pivots healthy, and save the cleaner until priority and setup threats are controlled."

    if not target_priority and opponent_species:
        target_priority.append(f"identify_primary_win_condition_against_{opponent_species[0]}")
    if own_species:
        lead_adjustments.append(f"start_from_own_core_{own_species[0]}")
    if knowledge_context and int(knowledge_context.get("result_count") or 0) > 0:
        risk_controls.append("cross_check_web_usage_before_committing")
    else:
        risk_controls.append("request_matchup_knowledge_when_preview_is_available")

    return {
        "opening_plan": opening_plan,
        "target_priority": list(dict.fromkeys(target_priority)),
        "lead_adjustments": list(dict.fromkeys(lead_adjustments)),
        "risk_controls": list(dict.fromkeys(risk_controls)),
        "confidence": "medium" if opponent_species else "low",
        "next_actions": ["review_preview", "choose_team" if battle_type == "double" else "choose_move", "autopilot"],
    }


def _build_showdown_mission_plan_snapshot(
    payload: ShowdownSessionMissionRequest,
    *,
    format_info,
    resolved_mode: str,
    mode_source: str,
    mode_recommendation: dict,
    learning_profile: dict,
) -> dict:
    team_species: list[str] = []
    team_source = "not_required"
    team_reason = f"{format_info.name} supplies teams on Pokemon Showdown."
    team_adjustments: list[dict[str, Any]] = []
    team_audit: dict[str, Any] = {}
    if isinstance(payload.team, list):
        team_species = [
            str(member.get("species") or member.get("name") or "Unknown")
            for member in payload.team
            if isinstance(member, dict)
        ]
        team_source = "provided"
        team_reason = "Using the team supplied in the mission planning payload."
    elif payload.team is None and format_info.requires_team:
        generated = pokemon_showdown_team_factory.generate(
            format_info.id,
            mode=resolved_mode,
            learning_profile=learning_profile,
        )
        if generated:
            team_species = generated.species()
            team_source = generated.source
            team_reason = generated.reason
            team_adjustments = generated.adjustments
            team_audit = generated.audit
        else:
            team_source = "unavailable"
            team_reason = f"No autonomous team builder is available for {format_info.name}."

    return {
        "username": payload.username,
        "battle_format": format_info.id,
        "showdown_format": format_info.showdown_format,
        "mode": resolved_mode,
        "requested_mode": payload.mode,
        "mode_source": mode_source,
        "mode_recommendation": mode_recommendation,
        "learning_profile": learning_profile,
        "team_species": team_species,
        "team_source": team_source,
        "team_reason": team_reason,
        "team_adjustments": team_adjustments,
        "team_audit": team_audit,
        "has_knowledge_context": bool(payload.auto_research_team and team_species),
    }


def _normalize_showdown_mission_goal(goal: str | None) -> str:
    normalized = (goal or "ladder").lower()
    if normalized not in {"auto", "prepare", "queue", "ladder", "learn"}:
        raise ValueError("mission_goal must be one of: auto, prepare, queue, ladder, learn.")
    return normalized


def _resolve_showdown_mission_policy(payload: ShowdownSessionMissionRequest, session: dict | None = None) -> dict:
    session = session or {}
    requested_goal = _normalize_showdown_mission_goal(payload.mission_goal)
    goal = requested_goal
    recommendation = _recommend_showdown_mission_goal(session)
    if goal == "auto":
        goal = recommendation["mission_goal"]
    presets = {
        "prepare": {
            "allowed_actions": ["research_team"],
            "stop_actions": ["research_team"],
            "auto_search": False,
            "stop_on_new_session": True,
        },
        "queue": {
            "allowed_actions": ["research_team", "start_search", "flush_pending"],
            "stop_actions": ["start_search"],
            "auto_search": True,
            "stop_on_new_session": True,
        },
        "ladder": {
            "allowed_actions": [
                "research_team",
                "connect",
                "flush_pending",
                "start_search",
                "accept_challenge",
                "run_once",
                "autopilot",
                "analyze",
                "new_session",
            ],
            "stop_actions": payload.stop_actions,
            "auto_search": True,
            "stop_on_new_session": payload.stop_on_new_session,
        },
        "learn": {
            "allowed_actions": [
                "research_team",
                "connect",
                "flush_pending",
                "start_search",
                "accept_challenge",
                "run_once",
                "autopilot",
                "analyze",
                "new_session",
            ],
            "stop_actions": payload.stop_actions,
            "auto_search": True,
            "stop_on_new_session": False,
        },
    }
    policy = dict(presets[goal])
    policy["mission_goal"] = goal
    policy["requested_mission_goal"] = requested_goal
    policy["mission_goal_source"] = recommendation["source"] if requested_goal == "auto" else "manual"
    policy["mission_goal_reason"] = recommendation["reason"] if requested_goal == "auto" else "Mission goal was selected manually."
    plan_actions, executable_plan_actions, unsupported_plan_actions = _resolve_showdown_training_plan_actions(session)
    training_tasks, task_actions, executable_task_actions, unsupported_task_actions = _resolve_showdown_training_task_actions(session)
    policy_evaluation, policy_actions, executable_policy_actions, unsupported_policy_actions = _resolve_showdown_policy_actions(
        session,
        mission_goal=goal,
    )
    policy["training_plan_actions"] = plan_actions
    policy["executable_plan_actions"] = executable_plan_actions
    policy["unsupported_plan_actions"] = unsupported_plan_actions
    policy["training_tasks"] = training_tasks
    policy["training_task_actions"] = task_actions
    policy["executable_task_actions"] = executable_task_actions
    policy["unsupported_task_actions"] = unsupported_task_actions
    policy["policy_evaluation"] = policy_evaluation
    policy["policy_actions"] = policy_actions
    policy["executable_policy_actions"] = executable_policy_actions
    policy["unsupported_policy_actions"] = unsupported_policy_actions
    team_audit = session.get("team_audit") or {}
    team_audit_gaps = [str(gap) for gap in team_audit.get("gaps") or [] if str(gap)]
    team_audit_actions = _resolve_showdown_team_audit_actions(session)
    policy["team_audit"] = team_audit
    policy["team_audit_actions"] = team_audit_actions
    policy["team_audit_gaps"] = team_audit_gaps
    live_readiness = session.get("live_readiness") or {}
    readiness_actions = _resolve_showdown_readiness_actions(session, mission_goal=goal)
    policy["live_readiness"] = live_readiness
    policy["readiness_status"] = live_readiness.get("status")
    policy["readiness_score"] = live_readiness.get("score")
    policy["readiness_actions"] = readiness_actions
    policy["require_live_readiness"] = goal in {"ladder", "learn"}
    policy["action_plan_source"] = "preset"
    if requested_goal == "auto" and recommendation["source"] == "live_readiness" and readiness_actions:
        policy["allowed_actions"] = readiness_actions
        policy["action_plan_source"] = "live_readiness"
    if requested_goal == "auto" and recommendation["source"] == "team_audit" and team_audit_actions:
        policy["allowed_actions"] = team_audit_actions
        policy["action_plan_source"] = "team_audit"
    if requested_goal == "auto" and recommendation["source"] == "training_plan" and executable_task_actions:
        policy["allowed_actions"] = executable_task_actions
        policy["action_plan_source"] = "training_tasks"
    elif requested_goal == "auto" and recommendation["source"] == "training_plan" and executable_plan_actions:
        policy["allowed_actions"] = executable_plan_actions
        policy["action_plan_source"] = "training_plan"
    if requested_goal == "auto" and recommendation["source"] == "policy_evaluation" and executable_policy_actions:
        policy["allowed_actions"] = executable_policy_actions
        policy["action_plan_source"] = "policy_evaluation"
    if requested_goal == "auto" and recommendation["source"] != "live_readiness" and readiness_actions and goal in {"queue", "ladder", "learn"}:
        policy["allowed_actions"] = list(dict.fromkeys(readiness_actions + policy["allowed_actions"]))
        if policy["action_plan_source"] == "preset":
            policy["action_plan_source"] = "live_readiness"
    if payload.allowed_actions:
        policy["allowed_actions"] = payload.allowed_actions
        policy["action_plan_source"] = "custom"
    if payload.stop_actions:
        policy["stop_actions"] = payload.stop_actions
    if payload.auto_search:
        policy["auto_search"] = True
    return policy


def _recommend_showdown_mission_goal(session: dict) -> dict[str, Any]:
    profile = session.get("learning_profile") or {}
    training_plan = profile.get("training_plan") or {}
    plan_goal = str(training_plan.get("next_mission_goal") or "").lower()
    battles = int(profile.get("battles") or 0)
    win_rate = float(profile.get("win_rate") or 0.0)
    average_reward = float(profile.get("average_reward") or 0.0)
    has_knowledge = bool(session.get("has_knowledge_context"))
    has_team_species = bool(session.get("team_species"))
    live_readiness_recommendation = _recommend_showdown_mission_goal_from_live_readiness(session)
    team_audit_recommendation = _recommend_showdown_mission_goal_from_team_audit(session)

    if live_readiness_recommendation:
        return live_readiness_recommendation
    if team_audit_recommendation:
        return team_audit_recommendation

    if has_team_species and not has_knowledge:
        return {
            "mission_goal": "prepare",
            "source": "knowledge_precheck",
            "reason": "Current generated team has no attached knowledge context yet.",
        }
    policy_recommendation = _recommend_showdown_mission_goal_from_policy_evaluation(session)
    if policy_recommendation:
        return policy_recommendation
    if plan_goal in {"prepare", "queue", "ladder", "learn"}:
        return {
            "mission_goal": plan_goal,
            "source": "training_plan",
            "reason": training_plan.get("reason") or "Learning profile training plan selected the next mission goal.",
        }
    if battles < 3:
        return {
            "mission_goal": "queue",
            "source": "sample_size",
            "reason": "Fewer than 3 completed battles are available, so collect baseline samples first.",
        }
    if win_rate < 0.45 or average_reward < 40:
        return {
            "mission_goal": "prepare",
            "source": "performance_guard",
            "reason": "Win rate or average reward is weak, so prepare before longer ladder runs.",
        }
    if win_rate >= 0.6 and average_reward >= 70:
        return {
            "mission_goal": "learn",
            "source": "performance_signal",
            "reason": "Win rate and reward are strong enough to continue learning loops.",
        }
    return {
        "mission_goal": "ladder",
        "source": "balanced_default",
        "reason": "Learning signals are stable enough for a bounded ladder run.",
    }


def _recommend_showdown_mission_goal_from_policy_evaluation(session: dict) -> dict[str, Any] | None:
    profile = session.get("learning_profile") or {}
    policy_evaluation = profile.get("policy_evaluation") or {}
    if not isinstance(policy_evaluation, dict) or not policy_evaluation:
        return None

    next_experiment = policy_evaluation.get("next_experiment") or {}
    mission_goal = str(next_experiment.get("mission_goal") or "").strip().lower()
    if mission_goal not in {"prepare", "queue", "ladder", "learn"}:
        phase = str(policy_evaluation.get("phase") or "").strip().lower()
        mission_goal = {
            "collect_data": "queue",
            "stabilize": "prepare",
            "explore": "ladder",
            "exploit": "learn",
        }.get(phase, "")
    if mission_goal not in {"prepare", "queue", "ladder", "learn"}:
        return None

    reason = str(next_experiment.get("reason") or "").strip()
    if not reason:
        phase = str(policy_evaluation.get("phase") or "policy").strip()
        recommended_mode = str(policy_evaluation.get("recommended_mode") or "balanced").strip()
        reason = f"Policy evaluation selected {mission_goal} from {phase} phase using {recommended_mode} mode."
    return {
        "mission_goal": mission_goal,
        "source": "policy_evaluation",
        "reason": reason,
        "policy_phase": policy_evaluation.get("phase"),
        "policy": policy_evaluation.get("policy"),
        "policy_confidence": policy_evaluation.get("confidence"),
        "policy_risk": policy_evaluation.get("risk"),
    }


def _recommend_showdown_mission_goal_from_live_readiness(session: dict) -> dict[str, Any] | None:
    live_readiness = session.get("live_readiness") or {}
    if live_readiness.get("status") != "blocked":
        return None

    blocked_checks = [
        check
        for check in live_readiness.get("checks") or []
        if isinstance(check, dict) and check.get("status") == "blocked"
    ]
    details = [
        str(check.get("detail") or check.get("label") or check.get("id"))
        for check in blocked_checks[:3]
        if str(check.get("detail") or check.get("label") or check.get("id"))
    ]
    reason = "; ".join(details) or str(live_readiness.get("recommendation") or "Live readiness is blocked.")
    return {
        "mission_goal": "prepare",
        "source": "live_readiness",
        "reason": f"{reason} Review live readiness before sending Showdown commands.",
    }


def _recommend_showdown_mission_goal_from_team_audit(session: dict) -> dict[str, Any] | None:
    team_audit = session.get("team_audit") or {}
    if not team_audit or not session.get("team_species"):
        return None

    status = str(team_audit.get("status") or "").lower()
    gaps = [str(gap) for gap in team_audit.get("gaps") or [] if str(gap)]
    raw_score = team_audit.get("score")
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 100.0
    has_knowledge = bool(session.get("has_knowledge_context"))

    should_prepare = status == "blocked" or score < 65 or (gaps and not has_knowledge)
    if not should_prepare:
        return None

    recommendation = str(team_audit.get("recommendation") or "").strip()
    gap_text = ", ".join(gaps[:4])
    if status == "blocked":
        detail = recommendation or "Generated team audit is blocked."
    elif score < 65:
        detail = recommendation or f"Generated team audit score is low ({score:.0f})."
    elif gap_text:
        detail = f"Generated team audit found role gap(s): {gap_text}."
        if recommendation:
            detail = f"{detail} {recommendation}"
    else:
        detail = recommendation or "Generated team audit recommends preparation before laddering."
    return {
        "mission_goal": "prepare",
        "source": "team_audit",
        "reason": f"{detail} Research or adjust the team before entering a longer ladder run.",
    }


def _resolve_showdown_readiness_actions(session: dict, *, mission_goal: str) -> list[str]:
    live_readiness = session.get("live_readiness") or {}
    if not live_readiness:
        return []

    supported_actions = {
        "review_readiness",
        "research_team",
        "connect",
        "flush_pending",
        "start_search",
        "accept_challenge",
        "run_once",
        "autopilot",
        "analyze",
        "new_session",
    }
    actions: list[str] = []

    def add(action: str | None) -> None:
        if action and action in supported_actions and action not in actions:
            actions.append(action)

    status = str(live_readiness.get("status") or "")
    if status == "blocked":
        add("review_readiness")
        for check in live_readiness.get("checks") or []:
            if isinstance(check, dict) and check.get("status") == "blocked":
                add(str(check.get("action") or ""))
        return actions

    if status != "action_required":
        return []

    for action in live_readiness.get("recommended_actions") or []:
        add(str(action))
    if mission_goal in {"ladder", "learn"}:
        add("autopilot")
    return actions


def _resolve_showdown_team_audit_actions(session: dict) -> list[str]:
    team_audit = session.get("team_audit") or {}
    if not team_audit or not session.get("team_species"):
        return []

    actions: list[str] = []
    if not session.get("has_knowledge_context"):
        actions.append("research_team")
    status = str(team_audit.get("status") or "").lower()
    raw_score = team_audit.get("score")
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 100.0
    if status == "blocked" or score < 65:
        actions.append("analyze")
    if not actions:
        actions.append("research_team")
    return list(dict.fromkeys(actions))


def _resolve_showdown_training_plan_actions(session: dict) -> tuple[list[str], list[str], list[str]]:
    profile = session.get("learning_profile") or {}
    training_plan = profile.get("training_plan") or {}
    plan_actions = [
        str(action).strip().lower()
        for action in training_plan.get("actions") or []
        if str(action).strip()
    ]
    executable, unsupported = _map_showdown_training_actions(plan_actions)
    return plan_actions, executable, unsupported


def _resolve_showdown_policy_actions(session: dict, *, mission_goal: str) -> tuple[dict, list[str], list[str], list[str]]:
    profile = session.get("learning_profile") or {}
    policy_evaluation = profile.get("policy_evaluation") or {}
    if not isinstance(policy_evaluation, dict) or not policy_evaluation:
        return {}, [], [], []

    phase = str(policy_evaluation.get("phase") or "").strip().lower()
    policy = str(policy_evaluation.get("policy") or "").strip().lower()
    risk = str(policy_evaluation.get("risk") or "").strip().lower()
    if phase == "collect_data" or mission_goal == "queue":
        actions = ["start_search"]
    elif phase == "stabilize" or mission_goal == "prepare" or risk == "high":
        actions = ["research_team", "analyze"]
    elif phase == "explore" or policy == "explore_under_sampled_mode" or mission_goal == "ladder":
        actions = ["start_search", "autopilot", "analyze"]
    else:
        actions = ["start_search", "autopilot", "analyze", "new_session"]

    executable, unsupported = _map_showdown_training_actions(actions)
    return policy_evaluation, actions, executable, unsupported


def _resolve_showdown_training_task_actions(session: dict) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    profile = session.get("learning_profile") or {}
    raw_tasks = profile.get("training_tasks") or []
    normalized_tasks: list[dict[str, Any]] = []
    task_actions: list[str] = []

    priority_rank = {"high": 0, "normal": 1, "low": 2}
    for index, task in enumerate(raw_tasks):
        if not isinstance(task, dict):
            continue
        action = str(task.get("action") or "").strip().lower()
        if not action:
            continue
        normalized_task = {
            "id": str(task.get("id") or f"task_{index + 1}_{action}"),
            "action": action,
            "priority": str(task.get("priority") or "normal"),
            "stage": str(task.get("stage") or ""),
            "evidence": str(task.get("evidence") or ""),
            "done_when": str(task.get("done_when") or ""),
        }
        normalized_tasks.append(normalized_task)

    normalized_tasks.sort(key=lambda item: (priority_rank.get(item["priority"], 1), item["id"]))
    for task in normalized_tasks:
        if task["action"] not in task_actions:
            task_actions.append(task["action"])

    executable, unsupported = _map_showdown_training_actions(task_actions)
    return normalized_tasks, task_actions, executable, unsupported


def _build_showdown_training_task_progress(
    training_tasks: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    *,
    stop_reason: str | None,
) -> dict[str, Any]:
    action_items = [
        {
            "id": task.get("id"),
            "action": str(task.get("action") or "").strip().lower(),
            "priority": task.get("priority"),
            "stage": task.get("stage"),
            "evidence": task.get("evidence"),
            "done_when": task.get("done_when"),
        }
        for task in training_tasks
    ]
    return _build_showdown_action_progress(
        action_items,
        steps,
        stop_reason=stop_reason,
        empty_recommendation="No training tasks were attached to this mission.",
        complete_recommendation="All mapped training tasks were observed in the supervisor steps.",
        partial_recommendation="Continue or review the next mission to finish pending task actions.",
        unsupported_recommendation="Training tasks need supported action mappings before the supervisor can execute them.",
        pending_recommendation="Supervisor stopped before the mapped training tasks were executed.",
    )


def _build_showdown_policy_action_progress(
    policy_actions: list[str],
    steps: list[dict[str, Any]],
    *,
    stop_reason: str | None,
) -> dict[str, Any]:
    action_items = [
        {
            "id": f"policy_{index + 1}_{action}",
            "action": str(action).strip().lower(),
            "priority": "normal",
            "stage": "policy",
            "evidence": "Policy evaluation selected this action for the mission.",
            "done_when": "The mapped supervisor action is observed without error.",
        }
        for index, action in enumerate(policy_actions)
        if str(action).strip()
    ]
    return _build_showdown_action_progress(
        action_items,
        steps,
        stop_reason=stop_reason,
        empty_recommendation="No policy actions were attached to this mission.",
        complete_recommendation="All mapped policy actions were observed in the supervisor steps.",
        partial_recommendation="Resume or continue the next mission to finish pending policy actions.",
        unsupported_recommendation="Policy actions need supported action mappings before the supervisor can execute them.",
        pending_recommendation="Supervisor stopped before the mapped policy actions were executed.",
    )


def _build_showdown_action_progress(
    action_items: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    *,
    stop_reason: str | None,
    empty_recommendation: str,
    complete_recommendation: str,
    partial_recommendation: str,
    unsupported_recommendation: str,
    pending_recommendation: str,
) -> dict[str, Any]:
    successful_actions = [
        str(step.get("action") or "")
        for step in steps
        if step.get("action") and not step.get("error")
    ]
    attempted_actions = [
        str(step.get("action") or "")
        for step in steps
        if step.get("action")
    ]
    error_step = next((step for step in steps if step.get("error")), None)
    task_results: list[dict[str, Any]] = []

    for task in action_items:
        action = str(task.get("action") or "").strip().lower()
        if not action:
            continue
        executable, unsupported = _map_showdown_training_actions([action])
        executed = [item for item in executable if item in successful_actions]
        missing = [item for item in executable if item not in successful_actions]

        if unsupported:
            status = "unsupported"
        elif not executable:
            status = "unsupported"
        elif not executed:
            status = "pending"
        elif missing:
            status = "partial"
        else:
            status = "completed"

        blocked_reason = None
        if status in {"pending", "partial"}:
            if error_step and error_step.get("error"):
                blocked_reason = str(error_step["error"])
            elif stop_reason:
                blocked_reason = f"Mission stopped with {stop_reason} before all mapped task actions completed."

        task_results.append({
            "id": task.get("id"),
            "action": action,
            "priority": task.get("priority"),
            "stage": task.get("stage"),
            "status": status,
            "mapped_actions": executable,
            "executed_actions": executed,
            "missing_actions": missing,
            "unsupported_actions": unsupported,
            "evidence": task.get("evidence"),
            "done_when": task.get("done_when"),
            "blocked_reason": blocked_reason,
        })

    completed_count = sum(1 for item in task_results if item["status"] == "completed")
    partial_count = sum(1 for item in task_results if item["status"] == "partial")
    pending_count = sum(1 for item in task_results if item["status"] == "pending")
    unsupported_count = sum(1 for item in task_results if item["status"] == "unsupported")
    task_count = len(task_results)

    if not task_count:
        status = "none"
        recommendation = empty_recommendation
    elif completed_count == task_count:
        status = "completed"
        recommendation = complete_recommendation
    elif completed_count or partial_count:
        status = "partial"
        recommendation = partial_recommendation
    elif unsupported_count == task_count:
        status = "unsupported"
        recommendation = unsupported_recommendation
    else:
        status = "pending"
        recommendation = pending_recommendation

    return {
        "status": status,
        "task_count": task_count,
        "completed_count": completed_count,
        "partial_count": partial_count,
        "pending_count": pending_count,
        "unsupported_count": unsupported_count,
        "executed_actions": list(dict.fromkeys(successful_actions)),
        "attempted_actions": list(dict.fromkeys(attempted_actions)),
        "stop_reason": stop_reason,
        "recommendation": recommendation,
        "tasks": task_results,
    }


def _map_showdown_training_actions(actions: list[str]) -> tuple[list[str], list[str]]:
    executable: list[str] = []
    unsupported: list[str] = []

    aliases = {
        "research_team": ["research_team"],
        "plan_adjustments": ["research_team"],
        "start_search": ["connect", "flush_pending", "start_search"],
        "queue_short_run": ["connect", "flush_pending", "start_search", "autopilot", "analyze"],
        "connect": ["connect"],
        "flush_pending": ["connect", "flush_pending"],
        "accept_challenge": ["accept_challenge", "connect", "flush_pending"],
        "run_once": ["connect", "flush_pending", "run_once"],
        "autopilot": ["connect", "flush_pending", "start_search", "autopilot"],
        "analyze": ["analyze"],
        "new_session": ["new_session"],
    }

    def add(action: str) -> None:
        if action not in executable:
            executable.append(action)

    for action in actions:
        mapped = aliases.get(action)
        if mapped is None and action.startswith("audit_"):
            mapped = ["analyze"]
        if mapped is None:
            unsupported.append(action)
            continue
        for item in mapped:
            add(item)
    return executable, unsupported


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


@router.get("/showdown/learning/mastery")
async def list_showdown_mastery_ranking(
    battle_format: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Rank learned Pokemon Showdown profiles by mastery score."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100.")
    normalized_format = None
    if battle_format:
        try:
            normalized_format = pokemon_format_catalog.get(battle_format).id
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await pokemon_showdown_learning_store.mastery_ranking(
        db,
        battle_format=normalized_format,
        limit=limit,
    )


@router.get("/showdown/formats/capabilities")
async def list_showdown_format_capabilities(
    username: str = "PokemonBot",
    include_learning: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Return autonomous Showdown capability coverage for every supported format."""
    capabilities = []
    for format_info in pokemon_format_catalog.list_formats():
        learning_profile = None
        if include_learning:
            learning_profile = await pokemon_showdown_learning_store.profile(
                db,
                username=username,
                battle_format=format_info.id,
            )
        capabilities.append(_build_showdown_format_capability(format_info, learning_profile))
    ready_count = sum(1 for item in capabilities if item["automation_readiness"] == "ready")
    return {
        "username": username,
        "format_count": len(capabilities),
        "ready_count": ready_count,
        "coverage_score": round((ready_count / len(capabilities)) * 100) if capabilities else 0,
        "formats": capabilities,
    }


@router.get("/showdown/tactical-briefing")
async def get_showdown_tactical_briefing(
    username: str = "PokemonBot",
    battle_format: str = "vgc2024",
    mode: str = "auto",
    include_knowledge: bool = False,
    max_results: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """Build a pre-battle tactical briefing from format, team, learning, and knowledge signals."""
    if max_results < 1 or max_results > 10:
        raise HTTPException(status_code=400, detail="max_results must be between 1 and 10.")
    try:
        return await _build_showdown_tactical_briefing(
            db,
            username=username,
            battle_format=battle_format,
            mode=mode,
            include_knowledge=include_knowledge,
            max_results=max_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if "Unsupported Pokemon battle format" in str(exc) else 400, detail=str(exc)) from exc


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


@router.get("/showdown/sessions/{session_id}/readiness")
async def get_showdown_session_readiness(session_id: str):
    """Get the live-play readiness audit for a Pokemon Showdown automation session."""
    session = pokemon_showdown_session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Pokemon Showdown session not found")
    snapshot = session.to_dict()
    return {
        "session_id": session.session_id,
        "username": session.username,
        "battle_format": session.battle_format,
        "showdown_format": session.showdown_format,
        "live_readiness": snapshot["live_readiness"],
        "next_actions": snapshot["next_actions"],
    }


@router.get("/showdown/sessions/{session_id}/matchup-briefing")
async def get_showdown_session_matchup_briefing(
    session_id: str,
    room_id: str | None = None,
    include_knowledge: bool = False,
    max_results: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """Build a matchup briefing from synced Showdown room preview and battlefield state."""
    if max_results < 1 or max_results > 10:
        raise HTTPException(status_code=400, detail="max_results must be between 1 and 10.")
    session = pokemon_showdown_session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Pokemon Showdown session not found")
    try:
        return await _build_showdown_matchup_briefing(
            db,
            session=session.to_dict(),
            room_id=room_id,
            include_knowledge=include_knowledge,
            max_results=max_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
            require_live_readiness=payload.require_live_readiness,
        )
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShowdownConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/showdown/sessions/{session_id}/next-action")
async def execute_showdown_session_next_action(
    session_id: str,
    payload: ShowdownSessionNextActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute one recommended Showdown session action for autonomous supervisors."""
    state = pokemon_showdown_session_service.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Pokemon Showdown session not found")

    action = payload.action
    if not action:
        next_actions = state.to_dict().get("next_actions") or []
        action = next_actions[0].get("action") if next_actions else None
    if not action:
        session = state.to_dict()
        return {
            "action": None,
            "session": session,
            "result": {"skipped": True, "reason": "No recommended action is available."},
        }

    try:
        result = await _execute_showdown_action(session_id, action, payload, db)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ShowdownConnectionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = result.get("session") or pokemon_showdown_session_service.get_session(session_id)
    if hasattr(session, "to_dict"):
        session = session.to_dict()
    return {
        "action": action,
        "session": session,
        "result": result,
        "analysis": result.get("analysis"),
        "learning_profile": result.get("learning_profile"),
        "knowledge_context": result.get("knowledge_context"),
    }


@router.post("/showdown/sessions/{session_id}/supervise")
async def supervise_showdown_session(
    session_id: str,
    payload: ShowdownSessionSupervisorRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a bounded sequence of recommended Showdown actions."""
    if payload.max_actions < 1 or payload.max_actions > 20:
        raise HTTPException(status_code=400, detail="max_actions must be between 1 and 20.")

    state = pokemon_showdown_session_service.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Pokemon Showdown session not found")

    current_session_id = session_id
    steps = []
    stop_reason = "max_actions"
    learning_profile = None
    analysis = None
    knowledge_context = None

    for index in range(payload.max_actions):
        state = pokemon_showdown_session_service.get_session(current_session_id)
        if not state:
            stop_reason = "session_missing"
            break

        snapshot = state.to_dict()
        action = (
            payload.action
            if index == 0 and payload.action
            else _select_showdown_supervisor_action(snapshot, payload)
        )
        if not action:
            stop_reason = "no_allowed_action"
            break

        step = {
            "index": index + 1,
            "session_id": current_session_id,
            "action": action,
            "status_before": snapshot.get("status"),
        }
        try:
            result = await _execute_showdown_action(current_session_id, action, payload, db)
        except (KeyError, ShowdownConnectionError, ValueError) as exc:
            refreshed = pokemon_showdown_session_service.get_session(current_session_id)
            step["error"] = str(exc)
            step["session"] = refreshed.to_dict() if refreshed else None
            steps.append(step)
            stop_reason = "error"
            if payload.stop_on_error:
                break
            continue

        session = _normalize_showdown_session_result(result.get("session"))
        step["session"] = session
        step["result"] = result
        step["status_after"] = session.get("status") if session else None
        step["next_actions"] = session.get("next_actions") if session else []
        steps.append(step)

        learning_profile = result.get("learning_profile") or learning_profile
        analysis = result.get("analysis") or (session or {}).get("analysis") or analysis
        knowledge_context = result.get("knowledge_context") or knowledge_context

        if action == "new_session" and session and session.get("session_id"):
            current_session_id = session["session_id"]
            if payload.stop_on_new_session:
                stop_reason = "new_session"
                break
        if payload.stop_actions and action in set(payload.stop_actions):
            stop_reason = "stop_action"
            break
        if payload.stop_on_finished and session and session.get("status") == "finished":
            stop_reason = "finished"
            break

    supervisor_summary = None
    final_state = pokemon_showdown_session_service.get_session(current_session_id)
    if final_state:
        supervisor_summary = pokemon_showdown_session_service.store_supervisor_summary(
            current_session_id,
            _build_showdown_supervisor_summary(
                original_session_id=session_id,
                session_id=current_session_id,
                status=final_state.status,
                stop_reason=stop_reason,
                steps=steps,
            ),
        )
    final_state = pokemon_showdown_session_service.get_session(current_session_id)
    final_session = final_state.to_dict() if final_state else None
    return {
        "session_id": current_session_id,
        "original_session_id": session_id,
        "session": final_session,
        "steps": steps,
        "step_count": len(steps),
        "stop_reason": stop_reason,
        "supervisor_summary": supervisor_summary,
        "analysis": analysis,
        "learning_profile": learning_profile,
        "knowledge_context": knowledge_context,
    }


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


async def _execute_showdown_action(
    session_id: str,
    action: str,
    payload: ShowdownSessionNextActionRequest,
    db: AsyncSession,
) -> dict:
    if action == "connect":
        return await pokemon_showdown_session_service.connect_session(session_id, send_pending=payload.send_commands)
    if action == "flush_pending":
        sent = await pokemon_showdown_session_service.flush_pending_commands(session_id)
        session = pokemon_showdown_session_service.get_session(session_id)
        return {"sent": sent, "session": session.to_dict() if session else None}
    if action == "run_once":
        result = await pokemon_showdown_session_service.run_once(
            session_id,
            auto_respond=True,
            send_commands=payload.send_commands,
        )
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
    if action == "autopilot":
        result = await pokemon_showdown_session_service.autopilot(
            session_id,
            max_messages=payload.max_messages,
            auto_search=payload.auto_search,
            send_commands=payload.send_commands,
            stop_on_finished=payload.stop_on_finished,
            stop_on_error=payload.stop_on_error,
            require_live_readiness=payload.require_live_readiness,
        )
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
    if action == "review_readiness":
        session = pokemon_showdown_session_service.get_session(session_id)
        if not session:
            raise KeyError(f"Pokemon Showdown session not found: {session_id}")
        return {
            "session": session.to_dict(),
            "live_readiness": session.to_dict().get("live_readiness"),
            "skipped": True,
            "reason": "Live readiness must be fixed before sending Showdown commands.",
        }
    if action == "start_search":
        commands = pokemon_showdown_session_service.start_ladder_search(session_id)
        session = pokemon_showdown_session_service.get_session(session_id)
        return {"commands": commands, "session": session.to_dict() if session else None}
    if action == "accept_challenge":
        commands = pokemon_showdown_session_service.accept_challenge(session_id)
        session = pokemon_showdown_session_service.get_session(session_id)
        return {"commands": commands, "session": session.to_dict() if session else None}
    if action == "research_team":
        if payload.max_results < 1 or payload.max_results > 10:
            raise ValueError("max_results must be between 1 and 10.")
        session = pokemon_showdown_session_service.get_session(session_id)
        if not session:
            raise KeyError(f"Pokemon Showdown session not found: {session_id}")
        if not session.team_species:
            raise ValueError("Showdown session has no team species to research.")
        context = await pokemon_knowledge_service.search_team(
            db,
            session.team_species,
            query_type="species_usage",
            max_results=payload.max_results,
        )
        updated = pokemon_showdown_session_service.attach_knowledge_context(session_id, context)
        return {"knowledge_context": context, "session": updated.to_dict()}
    if action == "analyze":
        analysis = pokemon_showdown_session_service.analyze_session(session_id)
        session = pokemon_showdown_session_service.get_session(session_id)
        result = {"analysis": analysis, "session": session.to_dict() if session else None}
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
    if action == "new_session":
        previous = pokemon_showdown_session_service.get_session(session_id)
        if not previous:
            raise KeyError(f"Pokemon Showdown session not found: {session_id}")
        resolved_mode, mode_source, mode_recommendation, learning_profile = await _resolve_showdown_mode(
            db,
            username=previous.username,
            battle_format=previous.battle_format,
            requested_mode=previous.requested_mode,
        )
        next_session = pokemon_showdown_session_service.create_session(
            username=previous.username,
            team=None,
            battle_format=previous.battle_format,
            mode=resolved_mode,
            requested_mode=previous.requested_mode,
            mode_source=mode_source,
            mode_recommendation=mode_recommendation,
            login_password=previous.login_password,
            auto_login=previous.auto_login,
            auto_accept_challenges=previous.auto_accept_challenges,
            auto_research_team=previous.auto_research_team,
            auto_search=False,
            learning_profile=learning_profile,
        )
        if previous.auto_research_team and next_session.team_species:
            context = await pokemon_knowledge_service.search_team(
                db,
                next_session.team_species,
                query_type="species_usage",
                max_results=payload.max_results,
            )
            next_session = pokemon_showdown_session_service.attach_knowledge_context(next_session.session_id, context)
        return {"session": next_session.to_dict(), "previous_session": previous.to_dict()}
    raise ValueError(f"Unsupported Showdown next action: {action}")


def _normalize_showdown_session_result(session):
    if hasattr(session, "to_dict"):
        return session.to_dict()
    return session


def _select_showdown_supervisor_action(session: dict, payload: ShowdownSessionSupervisorRequest) -> str | None:
    allowed_actions = set(payload.allowed_actions or [])
    for action in session.get("next_actions") or []:
        name = action.get("action")
        if not name:
            continue
        if allowed_actions and name not in allowed_actions:
            continue
        return name
    return None


def _build_showdown_supervisor_summary(
    *,
    original_session_id: str,
    session_id: str,
    status: str,
    stop_reason: str,
    steps: list[dict],
) -> dict:
    error_step = next((step for step in steps if step.get("error")), None)
    actions = [step.get("action") for step in steps if step.get("action")]
    return {
        "original_session_id": original_session_id,
        "session_id": session_id,
        "status": status,
        "stop_reason": stop_reason,
        "step_count": len(steps),
        "actions": actions,
        "last_action": actions[-1] if actions else None,
        "error": error_step.get("error") if isinstance(error_step, dict) else None,
    }


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
    policy_evaluation = profile.get("policy_evaluation") or {}
    policy_next_experiment = policy_evaluation.get("next_experiment") or {}
    recommended_mode = (
        policy_next_experiment.get("mode")
        or policy_evaluation.get("recommended_mode")
        or recommendation.get("mode")
    )
    source = "policy_evaluation" if policy_evaluation else "learning_profile"
    if recommended_mode not in allowed_modes:
        recommended_mode = "balanced"
        recommendation = {
            "mode": recommended_mode,
            "reason": "No reliable learned mode was available, so balanced was selected.",
        }
        source = "learning_profile"
    elif policy_evaluation:
        recommendation = {
            **recommendation,
            "mode": recommended_mode,
            "reason": policy_next_experiment.get("reason") or recommendation.get("reason"),
            "policy": policy_evaluation.get("policy"),
            "policy_phase": policy_evaluation.get("phase"),
            "policy_confidence": policy_evaluation.get("confidence"),
            "policy_risk": policy_evaluation.get("risk"),
        }
    return recommended_mode, source, recommendation, profile


# Data loading endpoint
@router.post("/init-data")
async def initialize_pokemon_data(db: AsyncSession = Depends(get_db)):
    """Initialize Pokemon data from JSON files"""
    loader = PokemonDataLoader(db)
    counts = await loader.load_all()
    return {"loaded": counts}
