from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.models.game import Game
from app.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws/games/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: str):
    await manager.connect_to_game(game_id, websocket)
    try:
        # 连接后发送当前游戏状态
        from app.core.database import async_session
        async with async_session() as db:
            result = await db.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            if game:
                await websocket.send_json({
                    "type": "game_state",
                    "data": {
                        "id": str(game.id),
                        "game_type": game.game_type,
                        "status": game.status,
                        "current_turn": game.config.get("current_turn", 0) if game.config else 0,
                        "config": game.config or {},
                    }
                })

        # 保持连接，接收客户端消息
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "set_speed":
                await websocket.send_json({
                    "type": "speed_changed",
                    "speed": data.get("speed", 3),
                })
    except WebSocketDisconnect:
        manager.disconnect_from_game(game_id, websocket)
    except Exception:
        manager.disconnect_from_game(game_id, websocket)
