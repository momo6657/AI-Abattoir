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
        "mission_goal": mission_policy["mission_goal"],
        "requested_mission_goal": mission_policy["requested_mission_goal"],
        "mission_goal_source": mission_policy["mission_goal_source"],
        "mission_goal_reason": mission_policy["mission_goal_reason"],
        "allowed_actions": mission_policy["allowed_actions"],
        "training_plan_actions": mission_policy["training_plan_actions"],
        "executable_plan_actions": mission_policy["executable_plan_actions"],
        "unsupported_plan_actions": mission_policy["unsupported_plan_actions"],
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
    )
    supervisor = await supervise_showdown_session(session.session_id, supervisor_payload, db)
    final_session = supervisor.get("session") or session.to_dict()
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
        "executable_plan_actions": mission_policy["executable_plan_actions"],
        "unsupported_plan_actions": mission_policy["unsupported_plan_actions"],
        "action_plan_source": mission_policy["action_plan_source"],
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
        **payload.model_dump(exclude={"rounds", "mastery_score_target", "stop_on_no_progress"})
    )
    rounds = []
    stop_reason = "round_limit"
    final_session = None
    latest_learning_profile = None
    latest_mastery_score = None

    for index in range(payload.rounds):
        plan = await plan_showdown_mission(mission_payload, db)
        mission = await start_showdown_mission(mission_payload, db)
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
            "session_id": (final_session or {}).get("session_id"),
            "status": (final_session or {}).get("status"),
            "mission_summary": mission_summary,
            "supervisor_stop_reason": supervisor.get("stop_reason"),
            "supervisor_step_count": supervisor.get("step_count", 0),
            "learning_profile": learning_profile,
            "mastery_score": latest_mastery_score,
        }
        rounds.append(round_summary)

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
                "last_goal": rounds[-1]["planned_goal"] if rounds else None,
                "last_goal_source": rounds[-1]["planned_goal_source"] if rounds else None,
                "rounds": [
                    {
                        "round": item["round"],
                        "planned_goal": item["planned_goal"],
                        "planned_goal_source": item["planned_goal_source"],
                        "supervisor_stop_reason": item["supervisor_stop_reason"],
                        "supervisor_step_count": item["supervisor_step_count"],
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
    if isinstance(payload.team, list):
        team_species = [
            str(member.get("species") or member.get("name") or "Unknown")
            for member in payload.team
            if isinstance(member, dict)
        ]
    elif payload.team is None and format_info.requires_team:
        team_species = ["generated_team"]

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
    policy["training_plan_actions"] = plan_actions
    policy["executable_plan_actions"] = executable_plan_actions
    policy["unsupported_plan_actions"] = unsupported_plan_actions
    policy["action_plan_source"] = "preset"
    if requested_goal == "auto" and recommendation["source"] == "training_plan" and executable_plan_actions:
        policy["allowed_actions"] = executable_plan_actions
        policy["action_plan_source"] = "training_plan"
    if payload.allowed_actions:
        policy["allowed_actions"] = payload.allowed_actions
        policy["action_plan_source"] = "custom"
    if payload.stop_actions:
        policy["stop_actions"] = payload.stop_actions
    if payload.auto_search:
        policy["auto_search"] = True
    return policy


def _recommend_showdown_mission_goal(session: dict) -> dict[str, str]:
    profile = session.get("learning_profile") or {}
    training_plan = profile.get("training_plan") or {}
    plan_goal = str(training_plan.get("next_mission_goal") or "").lower()
    battles = int(profile.get("battles") or 0)
    win_rate = float(profile.get("win_rate") or 0.0)
    average_reward = float(profile.get("average_reward") or 0.0)
    has_knowledge = bool(session.get("has_knowledge_context"))
    has_team_species = bool(session.get("team_species"))

    if has_team_species and not has_knowledge:
        return {
            "mission_goal": "prepare",
            "source": "knowledge_precheck",
            "reason": "Current generated team has no attached knowledge context yet.",
        }
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


def _resolve_showdown_training_plan_actions(session: dict) -> tuple[list[str], list[str], list[str]]:
    profile = session.get("learning_profile") or {}
    training_plan = profile.get("training_plan") or {}
    plan_actions = [
        str(action).strip().lower()
        for action in training_plan.get("actions") or []
        if str(action).strip()
    ]
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

    for action in plan_actions:
        mapped = aliases.get(action)
        if mapped is None and action.startswith("audit_"):
            mapped = ["analyze"]
        if mapped is None:
            unsupported.append(action)
            continue
        for item in mapped:
            add(item)
    return plan_actions, executable, unsupported


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
        )
        result["learning_profile"] = await _persist_showdown_learning(db, result)
        return result
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
