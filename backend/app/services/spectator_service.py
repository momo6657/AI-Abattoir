"""Spectator and replay service for conversations and games."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.conversation import Conversation, Message
from app.models.game import Game, GamePlayer
from app.models.agent import Agent
from app.services.game_engine import WEREWOLF_ROLE_NAMES
from app.websocket.manager import manager as ws_manager

logger = logging.getLogger(__name__)


class SpectatorService:
    """Handles real-time spectator broadcasts and replay retrieval."""

    def __init__(self):
        self.ws_manager = ws_manager
        self._spectate_connections: Dict[str, List[WebSocket]] = {}

    # ==================== Conversation Spectating ====================

    async def join_as_spectator(self, websocket: WebSocket, conversation_id: UUID):
        """加入对话观战频道"""
        channel = f"spectate_conv_{conversation_id}"
        await websocket.accept()
        if channel not in self._spectate_connections:
            self._spectate_connections[channel] = []
        self._spectate_connections[channel].append(websocket)
        logger.info("Spectator joined conversation %s, channel=%s", conversation_id, channel)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except Exception:
            pass
        finally:
            self._remove_spectator(websocket, channel)

    async def broadcast_to_spectators(
        self, conversation_id: str, event_type: str, data: dict
    ):
        """Broadcast a conversation event to all spectators."""
        message = {
            "type": event_type,
            "conversation_id": str(conversation_id),
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        channel = f"spectate_conv_{conversation_id}"
        await self._broadcast_to_channel(channel, message)

    async def broadcast_conversation_to_spectators(
        self, conversation_id: str, event_type: str, data: dict
    ):
        """Alias for broadcast_to_spectators."""
        await self.broadcast_to_spectators(conversation_id, event_type, data)

    # ==================== Game Spectating ====================

    async def join_game_as_spectator(self, websocket: WebSocket, game_id: UUID):
        """加入游戏观战频道"""
        channel = f"spectate_game_{game_id}"
        await websocket.accept()
        if channel not in self._spectate_connections:
            self._spectate_connections[channel] = []
        self._spectate_connections[channel].append(websocket)
        logger.info("Spectator joined game %s, channel=%s", game_id, channel)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except Exception:
            pass
        finally:
            self._remove_spectator(websocket, channel)

    async def broadcast_game_event(
        self, game_id: str, event_type: str, data: dict
    ):
        """Broadcast a game event to all spectators and game WebSocket connections."""
        message = {
            "type": event_type,
            "game_id": str(game_id),
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # 广播给游戏 WebSocket 通道
        await self.ws_manager.broadcast_to_game(game_id, message)
        # 广播给 spectate 通道
        channel = f"spectate_game_{game_id}"
        await self._broadcast_to_channel(channel, message)

    # ==================== Connection Management ====================

    async def connect_spectator(self, channel: str, websocket: WebSocket):
        """Accept and register a spectator WebSocket connection."""
        await websocket.accept()
        if channel not in self._spectate_connections:
            self._spectate_connections[channel] = []
        self._spectate_connections[channel].append(websocket)

    def disconnect_spectator(self, channel: str, websocket: WebSocket):
        """Remove a spectator WebSocket connection."""
        self._remove_spectator(websocket, channel)

    def _remove_spectator(self, websocket: WebSocket, channel: str):
        """Remove a spectator WebSocket connection by channel."""
        if channel in self._spectate_connections:
            self._spectate_connections[channel] = [
                ws for ws in self._spectate_connections[channel] if ws is not websocket
            ]
            if not self._spectate_connections[channel]:
                del self._spectate_connections[channel]

    async def _broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast a message to all spectators in a channel."""
        if channel not in self._spectate_connections:
            return
        payload = json.dumps(message, default=str)
        dead: List[WebSocket] = []
        for ws in self._spectate_connections[channel]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._spectate_connections[channel].remove(ws)
        if not self._spectate_connections[channel]:
            del self._spectate_connections[channel]

    # ==================== Replay ====================

    async def replay_conversation(
        self, db: AsyncSession, conversation_id: UUID
    ) -> Dict[str, Any]:
        """获取对话回放（完整消息历史）"""
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise ValueError("Conversation not found")

        # 加载消息
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = msg_result.scalars().all()

        # 批量加载 agent 信息
        agent_ids = {m.agent_id for m in messages if m.agent_id}
        agents_map: Dict[str, Any] = {}
        if agent_ids:
            agents_result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
            agents_map = {str(a.id): a for a in agents_result.scalars().all()}

        message_list = []
        for msg in messages:
            agent = agents_map.get(str(msg.agent_id)) if msg.agent_id else None
            message_list.append({
                "id": str(msg.id),
                "agent_id": str(msg.agent_id) if msg.agent_id else None,
                "agent_name": agent.name if agent else "System",
                "content": msg.content,
                "turn_number": getattr(msg, "turn_number", None),
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })

        return {
            "id": str(conv.id),
            "title": getattr(conv, "title", None),
            "mode": getattr(conv, "mode", None),
            "status": getattr(conv, "status", None),
            "messages": message_list,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
        }

    def _format_game_event_message(self, event: dict) -> tuple[str, str]:
        """把游戏事件转成回放和观战能读懂的中文。"""
        event_type = event.get("type", "unknown")
        data = event.get("data") or {}
        if data.get("message"):
            log_type = "elimination" if event_type in {"night_result", "vote_result"} and (
                data.get("deaths") or data.get("exiled")
            ) else "system"
            return str(data["message"]), log_type

        if event_type == "game_start":
            return f"游戏开始：{data.get('player_count', 0)} 名玩家入场。", "system"
        if event_type == "day_discussion":
            speeches = data.get("speeches") or []
            if speeches:
                lines = [f"{s.get('name', '玩家')}：{s.get('content', '')}" for s in speeches]
                return "白天讨论\n" + "\n".join(lines), "system"
            return "白天讨论完成。", "system"
        if event_type == "night_result":
            names = data.get("death_names") or data.get("deaths") or []
            return f"昨晚 {'、'.join(names)} 死亡。" if names else "昨晚是平安夜。", "elimination" if names else "system"
        if event_type == "vote_result":
            exiled = data.get("exiled_name") or data.get("exiled") or "玩家"
            return f"投票结果：{exiled} 被放逐。", "elimination"
        if event_type == "game_over":
            winner = data.get("winner")
            return "游戏结束：狼人阵营获胜。" if winner == "werewolf" else "游戏结束：村民阵营获胜。", "system"
        return str(event_type), "system"

    def _messages_from_game_events(self, events: list[dict]) -> list[dict]:
        messages: list[dict] = []
        for idx, event in enumerate(events):
            data = event.get("data") or {}
            event_type = event.get("type", "unknown")
            created_at = event.get("timestamp") or datetime.now(timezone.utc).isoformat()
            # 保存完整事件数据用于前端可视化回放
            game_data = {
                "event_type": event_type,
                "turn": event.get("turn"),
                **data,
            }
            if event_type == "day_discussion" and data.get("speeches"):
                for speech in data["speeches"]:
                    messages.append({
                        "id": f"{event_type}-{event.get('turn', 0)}-{speech.get('agent_id', idx)}",
                        "agent_id": speech.get("agent_id"),
                        "agent_name": speech.get("name") or "玩家",
                        "role": "agent",
                        "content": speech.get("content") or "",
                        "turn_number": event.get("turn"),
                        "log_type": "speech",
                        "game_data": {
                            "event_type": event_type,
                            "turn": event.get("turn"),
                            "players": data.get("players"),
                        },
                        "created_at": created_at,
                    })
                continue

            content, log_type = self._format_game_event_message(event)
            messages.append({
                "id": f"{event_type}-{event.get('turn', 0)}-{idx}",
                "agent_id": None,
                "agent_name": "系统",
                "role": "system",
                "content": content,
                "turn_number": event.get("turn"),
                "log_type": log_type,
                "game_data": game_data,
                "created_at": created_at,
            })
        return messages

    async def replay_game(
        self, db: AsyncSession, game_id: UUID
    ) -> Dict[str, Any]:
        """获取游戏回放"""
        result = await db.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        if not game:
            raise ValueError("Game not found")

        config = game.config or {}

        # 加载玩家
        players_result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = players_result.scalars().all()

        # 批量加载 agent 信息
        agent_ids = {p.agent_id for p in players if p.agent_id}
        agents_map: Dict[str, Any] = {}
        if agent_ids:
            agents_result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
            agents_map = {str(a.id): a for a in agents_result.scalars().all()}

        player_list = []
        for p in players:
            agent = agents_map.get(str(p.agent_id)) if p.agent_id else None
            player_list.append({
                "agent_id": str(p.agent_id),
                "agent_name": agent.name if agent else "Unknown",
                "name": agent.name if agent else "Unknown",
                "role": p.role,
                "role_name": WEREWOLF_ROLE_NAMES.get(p.role or "", p.role),
                "is_alive": p.is_alive,
                "alive": p.is_alive,
                "config": p.config or {},
            })

        if not player_list:
            for player in config.get("players", []) or []:
                role = player.get("role")
                player_list.append({
                    "agent_id": str(player.get("agent_id") or player.get("id") or ""),
                    "agent_name": player.get("agent_name") or player.get("name") or "Unknown",
                    "name": player.get("name") or player.get("agent_name") or "Unknown",
                    "role": role,
                    "role_name": player.get("role_name") or WEREWOLF_ROLE_NAMES.get(role or "", role),
                    "is_alive": player.get("alive", player.get("is_alive", True)),
                    "alive": player.get("alive", player.get("is_alive", True)),
                    "config": player.get("config") or {},
                })

        events = config.get("events") or []
        messages = self._messages_from_game_events(events)

        return {
            "game_id": str(game.id),
            "game_type": game.game_type.value if game.game_type else None,
            "title": game.title,
            "status": game.status.value if game.status else None,
            "state": config or game.state or {},
            "players": player_list,
            "messages": messages,
            "message_count": len(messages),
            "winner_id": str(game.winner_id) if game.winner_id else None,
            "created_at": game.created_at.isoformat() if game.created_at else None,
            "updated_at": game.updated_at.isoformat() if game.updated_at else None,
        }

    async def get_conversation_replay(
        self, conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a full conversation replay (legacy interface)."""
        async with async_session() as db:
            try:
                return await self.replay_conversation(db, UUID(conversation_id))
            except ValueError:
                return None

    async def get_game_replay(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a full game replay (legacy interface)."""
        async with async_session() as db:
            try:
                return await self.replay_game(db, UUID(game_id))
            except ValueError:
                return None


# Module-level singleton
spectator_service = SpectatorService()
