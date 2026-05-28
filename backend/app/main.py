from uuid import UUID
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import models, agents, conversations, games, auth, arena, search, hierarchy, evolution, leaderboard
from app.core.database import get_db, engine, Base
from app.core.config import settings
from app.websocket.manager import manager as ws_manager
from app.services.spectator_service import spectator_service
from app.websocket.game_ws import router as game_ws_router

# Import all models to register them with Base
from app.models import *  # noqa: F401, F403


@asynccontextmanager
async def lifespan(app):
    """Create database tables on startup if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="AI Abattoir", version="0.1.0", lifespan=lifespan, redirect_slashes=False)


# CORS configuration: read allowed origins from settings instead of wildcard
_allowed_origins = settings.allowed_origins_list
_cors_kwargs = {
    "allow_origins": _allowed_origins if _allowed_origins else ["*"],
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
# allow_credentials=True is only safe when origins are explicitly specified (not wildcard)
if _allowed_origins:
    _cors_kwargs["allow_credentials"] = True

app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, FastAPIHTTPException):
        raise exc
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(models.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(games.router)
app.include_router(arena.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(hierarchy.router, prefix="/api")
app.include_router(evolution.router, prefix="/api")
app.include_router(leaderboard.router, prefix="/api")
app.include_router(game_ws_router)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Health check with database status."""
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:100]}"

    return {
        "status": "ok",
        "database": db_status,
        "version": "0.1.0",
    }


@app.post("/api/seed")
async def seed_data(request: Request, db: AsyncSession = Depends(get_db)):
    """Seed database with initial models and agents. Call once after deployment."""
    # Simple auth check - require X-Seed-Key header
    seed_key = request.headers.get("X-Seed-Key", "")
    if seed_key != os.getenv("SEED_KEY", "ai-abattoir-seed-2025"):
        raise HTTPException(status_code=403, detail="Invalid seed key")
    from sqlalchemy import select, func
    from app.models.model import Model, ModelCapability, CapabilityType
    from app.models.agent import Agent, AgentProfile

    # Check if already seeded
    count = await db.execute(select(func.count()).select_from(Model))
    if count.scalar() > 0:
        return {"message": "Database already seeded", "models": count.scalar()}

    # Create models (API keys from environment or hardcoded for demo)
    gpt_key = os.getenv("GPT54_API_KEY", "")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    llm_base = os.getenv("LLM_API_BASE", "https://api.vip.crond.dev/v1")

    models_data = [
        {
            "name": "GPT-5.4",
            "provider": "openai",
            "model_id": "openai/gpt-5.4",
            "api_key": gpt_key,
            "api_base": llm_base,
            "capabilities": [CapabilityType.TEXT_GENERATION, CapabilityType.IMAGE_UNDERSTANDING, CapabilityType.CODE_EXECUTION],
        },
        {
            "name": "DeepSeek-V4-Pro",
            "provider": "deepseek",
            "model_id": "openai/deepseek-v4-pro",
            "api_key": deepseek_key,
            "api_base": llm_base,
            "capabilities": [CapabilityType.TEXT_GENERATION, CapabilityType.CODE_EXECUTION],
        },
    ]

    model_map = {}
    for m in models_data:
        model = Model(
            name=m["name"],
            provider=m["provider"],
            model_id=m["model_id"],
            api_key=m["api_key"],
            api_base=m["api_base"],
            is_active=True,
            status="online",
        )
        db.add(model)
        await db.flush()
        for cap in m["capabilities"]:
            db.add(ModelCapability(model_id=model.id, capability=cap))
        model_map[m["name"]] = model.id

    # Create agents
    agents_data = [
        {
            "name": "谋略家",
            "description": "擅长分析和制定策略",
            "model_name": "GPT-5.4",
            "profile": {
                "persona": "你是一位深谋远虑的谋略家",
                "personality": "冷静、理性、善于洞察本质",
                "speaking_style": "逻辑严密，善用历史典故",
                "background_story": "曾参与无数次重大决策",
                "strengths": ["战略分析", "风险评估", "局势判断"],
            },
        },
        {
            "name": "创意大师",
            "description": "天马行空的想象力",
            "model_name": "DeepSeek-V4-Pro",
            "profile": {
                "persona": "你是一位充满创意的大脑",
                "personality": "好奇、开放、富有想象力",
                "speaking_style": "生动活泼，善用比喻",
                "background_story": "在艺术和科技的交叉点探索",
                "strengths": ["创意构思", "跨界联想", "故事创作"],
            },
        },
        {
            "name": "谈判专家",
            "description": "精通博弈论和沟通技巧",
            "model_name": "GPT-5.4",
            "profile": {
                "persona": "你是一位经验丰富的谈判专家",
                "personality": "善于倾听、有同理心",
                "speaking_style": "温和但有力",
                "background_story": "处理过无数复杂谈判",
                "strengths": ["谈判技巧", "情绪管理", "共识构建"],
            },
        },
        {
            "name": "执行者",
            "description": "高效执行任务，注重细节",
            "model_name": "DeepSeek-V4-Pro",
            "profile": {
                "persona": "你是一位雷厉风行的执行者",
                "personality": "果断、务实、注重细节",
                "speaking_style": "简洁明了，直击要点",
                "background_story": "经手的任务都能按时保质完成",
                "strengths": ["任务分解", "进度管控", "质量保证"],
            },
        },
    ]

    for a in agents_data:
        model_id = model_map.get(a["model_name"])
        if not model_id:
            continue
        agent = Agent(name=a["name"], description=a["description"], model_id=model_id)
        db.add(agent)
        await db.flush()
        p = a["profile"]
        db.add(AgentProfile(
            agent_id=agent.id,
            persona=p["persona"],
            personality=p["personality"],
            speaking_style=p["speaking_style"],
            background_story=p["background_story"],
            strengths=p["strengths"],
        ))

    await db.commit()
    return {"message": "Seed completed", "models": len(models_data), "agents": len(agents_data)}


@app.websocket("/ws/conversations/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: UUID):
    await ws_manager.connect(websocket, conversation_id)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, conversation_id)


# ========== 观战 WebSocket 端点 ==========


@app.websocket("/ws/spectate/conversation/{conversation_id}")
async def spectate_conversation(websocket: WebSocket, conversation_id: UUID):
    """观战对话 - 只接收消息，不发送"""
    await spectator_service.join_as_spectator(websocket, conversation_id)


@app.websocket("/ws/spectate/game/{game_id}")
async def spectate_game(websocket: WebSocket, game_id: UUID):
    """观战游戏 - 只接收消息，不发送"""
    await spectator_service.join_game_as_spectator(websocket, game_id)


# ========== 回放 API ==========


@app.get("/api/replay/conversations/{conversation_id}")
async def replay_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取对话回放（完整消息历史）"""
    try:
        data = await spectator_service.replay_conversation(db, conversation_id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/replay/games/{game_id}")
async def replay_game(
    game_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取游戏回放"""
    try:
        data = await spectator_service.replay_game(db, game_id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
