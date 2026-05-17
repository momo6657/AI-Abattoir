from uuid import UUID
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import models, agents, conversations, games, auth, arena, search
from app.core.database import get_db, engine, Base
from app.core.config import settings
from app.websocket.manager import ws_manager
from app.services.spectator_service import spectator_service

# Import all models to register them with Base
from app.models import *  # noqa: F401, F403

app = FastAPI(title="AI Abattoir", version="0.1.0")


@app.on_event("startup")
async def startup():
    """Create database tables on startup if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(models.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(games.router, prefix="/api")
app.include_router(arena.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(search.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


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
