from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timezone
import asyncio

from app.core.database import get_db
from app.models.game import Game, GameType, GameStatus
from app.models.agent import Agent
from app.schemas.game import GameCreate, GameResponse, EndGameRequest

router = APIRouter(prefix="/api/games", tags=["games"])

# 内存中的运行中游戏引擎实例
_running_games: dict[str, "GameEngine"] = {}


def _parse_game_uuid(game_id: str) -> UUID:
    try:
        return UUID(str(game_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="游戏 ID 无效")


def _compact_game_event(event: dict) -> dict:
    data = event.get("data") or {}
    return {
        "type": event.get("type", "unknown"),
        "turn": event.get("turn", 0),
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _append_game_event(config: dict, event: dict) -> dict:
    events = list(config.get("events") or [])
    events.append(_compact_game_event(event))
    config["events"] = events[-80:]
    return config


def _apply_game_event_to_config(config: dict, event: dict, engine: "GameEngine") -> dict:
    """把游戏引擎事件折叠成前端面板可直接消费的 config 快照。"""
    event_type = event.get("type", "unknown")
    data = event.get("data") or {}

    config = {
        **config,
        "current_turn": engine.current_turn,
        "last_event": _compact_game_event(event),
    }
    config = _append_game_event(config, event)

    if event_type == "game_start":
        config["phase"] = "night"
        config["game_started_at"] = datetime.now(timezone.utc).isoformat()
    elif event_type == "night_result":
        config["phase"] = data.get("phase", "day")
        config["last_deaths"] = data.get("deaths", [])
        config["night_result"] = data
    elif event_type == "vote_result":
        config["phase"] = "night"
        config["vote_result"] = data
    elif event_type in {"turn_result", "invalid_move"}:
        board = data.get("board")
        if board:
            config["board"] = board
        if data.get("last_move"):
            config["last_move"] = data.get("last_move")
        if "in_check" in data:
            config["in_check"] = data.get("in_check")
        config["last_move_result"] = data
    elif event_type == "debate_opening":
        config["topic"] = data.get("topic")
        config["current_phase"] = "opening"
        config["rounds"] = [
            {"phase": "opening", "side": "pro", "content": data.get("pro", "")},
            {"phase": "opening", "side": "con", "content": data.get("con", "")},
        ]
    elif event_type == "debate_cross":
        config["current_phase"] = "cross"
        rounds = list(config.get("rounds") or [])
        rounds.extend([
            {"phase": "cross_examination", "side": "pro", "content": data.get("pro_question", "")},
            {"phase": "cross_response", "side": "con", "content": data.get("con_answer", "")},
            {"phase": "cross_examination", "side": "con", "content": data.get("con_question", "")},
            {"phase": "cross_response", "side": "pro", "content": data.get("pro_answer", "")},
        ])
        config["rounds"] = rounds
    elif event_type == "debate_closing":
        config["current_phase"] = "closing"
        rounds = list(config.get("rounds") or [])
        rounds.extend([
            {"phase": "closing", "side": "pro", "content": data.get("pro", "")},
            {"phase": "closing", "side": "con", "content": data.get("con", "")},
        ])
        config["rounds"] = rounds
    elif event_type == "debate_result":
        config["current_phase"] = "result"
        config["scores"] = data
        if data.get("topic"):
            config["topic"] = data.get("topic")
    elif event_type == "scene":
        config["scene"] = data.get("scene", "")
        config["options"] = data.get("options", {})
        config["adventure_state"] = data.get("state")
    elif event_type == "action_result":
        config["last_result"] = data
        config["adventure_state"] = data.get("state")
    elif event_type == "negotiation_turn":
        turns = list(config.get("turns") or [])
        turns.append(data)
        config["turns"] = turns
        if data.get("proposal"):
            config["current_proposal"] = data.get("proposal")
    elif event_type == "deal_reached":
        config["deal_reached"] = data.get("proposal")
        config["current_proposal"] = data.get("proposal")
    elif event_type == "negotiation_failed":
        config["deal_reached"] = None
        config["current_proposal"] = data.get("last_proposal")
    elif event_type == "negotiation_scores":
        config["scores"] = data
    elif event_type == "game_over":
        config["game_over"] = data
        winner_id = data.get("winner_id") or data.get("winner")
        if winner_id:
            config["winner_id"] = winner_id
    elif event_type in {"error", "turn_error", "turn_timeout"}:
        config["runtime_error"] = data.get("message") or event.get("error") or event_type

    return config


def _enrich_game_response(game: Game) -> GameResponse:
    """从 Game ORM 对象构建完整 GameResponse"""
    config = game.config or {}
    status = GameStatus.PAUSED if config.get("paused_at") and game.status == GameStatus.IN_PROGRESS else game.status
    return GameResponse(
        id=str(game.id),
        game_type=game.game_type,
        title=game.title or "",
        status=status,
        config=config,
        players=config.get("players", []),
        current_turn=config.get("current_turn", 0),
        max_turns=config.get("max_turns", 20),
        winner_id=config.get("winner_id"),
        created_at=game.created_at,
        updated_at=game.updated_at,
    )


@router.get("", response_model=list[GameResponse])
async def list_games(
    game_type: GameType | None = None,
    status: GameStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Game)
    if game_type:
        query = query.where(Game.game_type == game_type)
    if status and status != GameStatus.PAUSED:
        query = query.where(Game.status == status)
    query = query.order_by(Game.created_at.desc())
    result = await db.execute(query)
    games = result.scalars().all()
    responses = [_enrich_game_response(g) for g in games]
    if status == GameStatus.PAUSED:
        return [game for game in responses if game.status == GameStatus.PAUSED]
    return responses


@router.post("", response_model=GameResponse)
async def create_game(game_data: GameCreate, db: AsyncSession = Depends(get_db)):
    game_dict = game_data.model_dump()
    agent_ids = game_dict.pop("agent_ids", [])
    max_turns = game_dict.pop("max_turns", 20)

    # 将 UUID 转为字符串
    agent_id_strs = [str(aid) for aid in agent_ids]

    game = Game(
        game_type=game_dict["game_type"],
        title=game_dict["title"],
        status=GameStatus.WAITING,
        config={
            **game_dict.get("config", {}),
            "max_turns": max_turns,
            "agent_ids": agent_id_strs,
        },
    )

    # 获取 agent 信息填充 players
    players = []
    if agent_id_strs:
        result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        agents = result.scalars().all()
        for agent in agents:
            players.append({"agent_id": str(agent.id), "name": agent.name})

    game.config["players"] = players
    db.add(game)
    await db.commit()
    await db.refresh(game)

    return _enrich_game_response(game)


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(game_id: str, db: AsyncSession = Depends(get_db)):
    game_uuid = _parse_game_uuid(game_id)
    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    return _enrich_game_response(game)


@router.put("/{game_id}", response_model=GameResponse)
async def update_game(
    game_id: str,
    status: GameStatus | None = None,
    winner_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    game_uuid = _parse_game_uuid(game_id)
    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    if status is not None:
        game.status = status
    if winner_id is not None:
        game.config = {**(game.config or {}), "winner_id": winner_id}

    await db.commit()
    await db.refresh(game)
    return _enrich_game_response(game)


@router.post("/{game_id}/end", response_model=GameResponse)
async def end_game(
    game_id: str,
    request: EndGameRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    game_uuid = _parse_game_uuid(game_id)
    game_key = str(game_uuid)
    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    game.status = GameStatus.FINISHED
    game.config = {
        key: value
        for key, value in (game.config or {}).items()
        if key != "paused_at"
    }
    if request and request.winner_id:
        game.config["winner_id"] = str(request.winner_id)

    # 停止运行中的引擎
    if game_key in _running_games:
        _running_games[game_key].stop()

    await db.commit()
    await db.refresh(game)
    return _enrich_game_response(game)


@router.post("/{game_id}/start", response_model=GameResponse)
async def start_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """启动游戏，自动运行所有回合"""
    game_uuid = _parse_game_uuid(game_id)
    game_key = str(game_uuid)
    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    if game.status == GameStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="游戏已在进行中")

    game.status = GameStatus.IN_PROGRESS
    await db.commit()
    await db.refresh(game)

    # 加载 agent 对象
    agent_ids = game.config.get("agent_ids", [])
    agents = []
    if agent_ids:
        from uuid import UUID as _UUID
        uuid_ids = []
        for aid in agent_ids:
            try:
                uuid_ids.append(_UUID(aid) if isinstance(aid, str) else aid)
            except (ValueError, TypeError):
                continue
        if uuid_ids:
            agents_result = await db.execute(select(Agent).where(Agent.id.in_(uuid_ids)))
            agents = agents_result.scalars().all()

    # 创建引擎并在后台运行
    from app.services.game_engine import GameEngine
    from app.services.llm_adapter import llm_adapter
    from app.services.spectator_service import spectator_service

    engine = GameEngine(
        game_type=game.game_type,
        agent_ids=agent_ids,
        config=game.config,
        llm_service=llm_adapter,
        spectator_service=spectator_service,
    )
    engine.agents = agents  # 注入 agent 对象供游戏引擎使用

    # 预加载模型信息供 LLM 调用
    if agents:
        from app.models.model import Model as ModelORM
        model_ids = list({a.model_id for a in agents if a.model_id})
        if model_ids:
            models_result = await db.execute(select(ModelORM).where(ModelORM.id.in_(model_ids)))
            models_list = models_result.scalars().all()
            engine._models_cache = {str(m.id): m for m in models_list}

    _running_games[game_key] = engine

    asyncio.create_task(_run_game_background(game_key, engine))

    return _enrich_game_response(game)


@router.post("/{game_id}/pause", response_model=GameResponse)
async def pause_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """暂停游戏"""
    game_uuid = _parse_game_uuid(game_id)
    game_key = str(game_uuid)
    if game_key in _running_games:
        _running_games[game_key].pause()

    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    game.config = {
        **(game.config or {}),
        "paused_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.commit()
    await db.refresh(game)
    return _enrich_game_response(game)


@router.post("/{game_id}/resume", response_model=GameResponse)
async def resume_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """恢复游戏"""
    game_uuid = _parse_game_uuid(game_id)
    game_key = str(game_uuid)
    if game_key in _running_games:
        _running_games[game_key].resume()

    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    game.status = GameStatus.IN_PROGRESS
    game.config = {
        key: value
        for key, value in (game.config or {}).items()
        if key != "paused_at"
    }
    await db.commit()
    await db.refresh(game)
    return _enrich_game_response(game)


async def _run_game_background(game_id: str, engine: "GameEngine"):
    """后台运行游戏，通过 WebSocket 推送事件"""
    from app.services.spectator_service import SpectatorService

    spectator_service = SpectatorService()
    game_uuid = UUID(game_id)

    async for event in engine.auto_run():
        event_type = event.get("type", "unknown")
        status_value = GameStatus.IN_PROGRESS.value
        config_snapshot: dict = {}

        from app.core.database import async_session
        async with async_session() as db:
            result = await db.execute(select(Game).where(Game.id == game_uuid))
            game = result.scalar_one_or_none()
            if game:
                config = _apply_game_event_to_config(dict(game.config or {}), event, engine)

                if event_type == "game_over":
                    game.status = GameStatus.FINISHED
                    winner_id = config.get("winner_id")
                    if winner_id:
                        config["winner_id"] = winner_id
                elif event_type in {
                    "max_turns_reached",
                    "debate_result",
                    "negotiation_scores",
                    "negotiation_failed",
                }:
                    game.status = GameStatus.FINISHED
                elif event_type in {"error", "turn_error", "turn_timeout"}:
                    game.status = GameStatus.CANCELLED

                game.config = config
                config_snapshot = config
                status_value = _enrich_game_response(game).status.value
                await db.commit()

        await spectator_service.broadcast_game_event(
            game_id,
            event_type,
            {
                **event,
                "current_turn": engine.current_turn,
                "status": status_value,
                "config": config_snapshot,
            },
        )

    # 清理
    _running_games.pop(game_id, None)
