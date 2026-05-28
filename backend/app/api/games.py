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


def _enrich_game_response(game: Game) -> GameResponse:
    """从 Game ORM 对象构建完整 GameResponse"""
    config = game.config or {}
    return GameResponse(
        id=str(game.id),
        game_type=game.game_type,
        title=game.title or "",
        status=game.status,
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
    if status:
        query = query.where(Game.status == status)
    query = query.order_by(Game.created_at.desc())
    result = await db.execute(query)
    games = result.scalars().all()
    return [_enrich_game_response(g) for g in games]


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
    result = await db.execute(select(Game).where(Game.id == game_id))
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
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    if status is not None:
        game.status = status
    if winner_id is not None:
        game.config["winner_id"] = winner_id

    await db.commit()
    await db.refresh(game)
    return _enrich_game_response(game)


@router.post("/{game_id}/end", response_model=GameResponse)
async def end_game(
    game_id: str,
    request: EndGameRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    game.status = GameStatus.FINISHED
    if request and request.winner_id:
        game.config["winner_id"] = str(request.winner_id)

    # 停止运行中的引擎
    if game_id in _running_games:
        _running_games[game_id].stop()

    await db.commit()
    await db.refresh(game)
    return _enrich_game_response(game)


@router.post("/{game_id}/start", response_model=GameResponse)
async def start_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """启动游戏，自动运行所有回合"""
    result = await db.execute(select(Game).where(Game.id == game_id))
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

    _running_games[game_id] = engine

    asyncio.create_task(_run_game_background(game_id, engine))

    return _enrich_game_response(game)


@router.post("/{game_id}/pause", response_model=GameResponse)
async def pause_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """暂停游戏"""
    if game_id in _running_games:
        _running_games[game_id].pause()

    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    game.status = GameStatus.PAUSED
    game.paused_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(game)
    return _enrich_game_response(game)


@router.post("/{game_id}/resume", response_model=GameResponse)
async def resume_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """恢复游戏"""
    if game_id in _running_games:
        _running_games[game_id].resume()

    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    game.status = GameStatus.IN_PROGRESS
    game.paused_at = None
    await db.commit()
    await db.refresh(game)
    return _enrich_game_response(game)


async def _run_game_background(game_id: str, engine: "GameEngine"):
    """后台运行游戏，通过 WebSocket 推送事件"""
    from app.services.spectator_service import SpectatorService

    spectator_service = SpectatorService()

    async for event in engine.auto_run():
        # 广播事件给观战者
        await spectator_service.broadcast_game_event(
            game_id, event.get("type", "unknown"), event
        )

        # 更新数据库
        from app.core.database import async_session
        async with async_session() as db:
            result = await db.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            if game:
                game.config["current_turn"] = engine.current_turn
                if event.get("type") == "game_over":
                    game.status = GameStatus.FINISHED
                    winner_id = event.get("data", {}).get("winner_id")
                    if winner_id:
                        game.config["winner_id"] = winner_id
                elif event.get("type") == "max_turns_reached":
                    game.status = GameStatus.FINISHED
                await db.commit()

    # 清理
    _running_games.pop(game_id, None)
