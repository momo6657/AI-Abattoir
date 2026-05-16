import json
from uuid import UUID
from typing import Dict, List, Optional, Any
from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.models.game import Game, GamePlayer
from app.models.agent import Agent


class SpectatorService:
    """观战服务 - 允许用户以只读方式观看对话和游戏"""

    def __init__(self):
        self._spectators: Dict[str, List[WebSocket]] = {}

    async def join_as_spectator(self, websocket: WebSocket, conversation_id: UUID):
        """以观战者身份加入对话（只接收消息，不发送）"""
        await websocket.accept()
        key = f"conv:{conversation_id}"
        if key not in self._spectators:
            self._spectators[key] = []
        self._spectators[key].append(websocket)

        try:
            # 观战者只接收消息，不发送
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except Exception:
            pass
        finally:
            self._remove_spectator(websocket, key)

    async def join_game_as_spectator(self, websocket: WebSocket, game_id: UUID):
        """以观战者身份加入游戏（只接收消息，不发送）"""
        await websocket.accept()
        key = f"game:{game_id}"
        if key not in self._spectators:
            self._spectators[key] = []
        self._spectators[key].append(websocket)

        try:
            # 观战者只接收消息，不发送
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except Exception:
            pass
        finally:
            self._remove_spectator(websocket, key)

    async def broadcast_to_spectators(self, target_key: str, data: dict):
        """向指定目标的所有观战者广播消息"""
        if target_key not in self._spectators:
            return
        payload = json.dumps(data, default=str)
        dead: List[WebSocket] = []
        for ws in self._spectators[target_key]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._spectators[target_key].remove(ws)

    async def broadcast_conversation_to_spectators(
        self, conversation_id: UUID, data: dict
    ):
        """向对话观战者广播"""
        await self.broadcast_to_spectators(f"conv:{conversation_id}", data)

    async def broadcast_game_to_spectators(self, game_id: UUID, data: dict):
        """向游戏观战者广播"""
        await self.broadcast_to_spectators(f"game:{game_id}", data)

    def get_spectator_count(self, conversation_id: UUID) -> int:
        """获取对话观战人数"""
        key = f"conv:{conversation_id}"
        return len(self._spectators.get(key, []))

    def get_game_spectator_count(self, game_id: UUID) -> int:
        """获取游戏观战人数"""
        key = f"game:{game_id}"
        return len(self._spectators.get(key, []))

    async def replay_conversation(
        self, db: AsyncSession, conversation_id: UUID
    ) -> Dict[str, Any]:
        """获取对话回放（完整消息历史）"""
        conversation = await db.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = result.scalars().all()

        message_list = []
        for msg in messages:
            agent = await db.get(Agent, msg.agent_id) if msg.agent_id else None
            message_list.append({
                "id": str(msg.id),
                "agent_id": str(msg.agent_id) if msg.agent_id else None,
                "agent_name": agent.name if agent else "System",
                "role": msg.role,
                "content": msg.content,
                "turn_number": msg.turn_number,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })

        return {
            "conversation_id": str(conversation.id),
            "title": conversation.title,
            "mode": conversation.mode.value if conversation.mode else None,
            "status": conversation.status.value if conversation.status else None,
            "message_count": len(message_list),
            "messages": message_list,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        }

    async def replay_game(
        self, db: AsyncSession, game_id: UUID
    ) -> Dict[str, Any]:
        """获取游戏回放"""
        game = await db.get(Game, game_id)
        if not game:
            raise ValueError("Game not found")

        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        player_list = []
        for p in players:
            agent = await db.get(Agent, p.agent_id)
            player_list.append({
                "agent_id": str(p.agent_id),
                "agent_name": agent.name if agent else "Unknown",
                "role": p.role,
                "is_alive": bool(p.is_alive),
                "config": p.config or {},
            })

        return {
            "game_id": str(game.id),
            "game_type": game.game_type.value if game.game_type else None,
            "title": game.title,
            "status": game.status.value if game.status else None,
            "state": game.state or {},
            "players": player_list,
            "winner_id": str(game.winner_id) if game.winner_id else None,
            "created_at": game.created_at.isoformat() if game.created_at else None,
            "updated_at": game.updated_at.isoformat() if game.updated_at else None,
        }

    def _remove_spectator(self, websocket: WebSocket, key: str):
        """移除观战者连接"""
        if key in self._spectators:
            self._spectators[key] = [
                ws for ws in self._spectators[key] if ws is not websocket
            ]
            if not self._spectators[key]:
                del self._spectators[key]


spectator_service = SpectatorService()
