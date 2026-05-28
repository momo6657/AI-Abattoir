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
from app.websocket.manager import manager as ws_manager

logger = logging.getLogger(__name__)


class SpectatorService:
    """Handles real-time spectator broadcasts and replay retrieval."""

    def __init__(self):
        self.ws_manager = ws_manager
        self._spectate_connections: Dict[str, List[WebSocket]] = {}

    # ==================== Conversation Spectating ====================

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
        if channel in self._spectate_connections:
            payload = json.dumps(message, default=str)
            dead: List[WebSocket] = []
            for ws in self._spectate_connections[channel]:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._spectate_connections[channel].remove(ws)

    async def broadcast_conversation_to_spectators(
        self, conversation_id: str, event_type: str, data: dict
    ):
        """Alias for broadcast_to_spectators."""
        await self.broadcast_to_spectators(conversation_id, event_type, data)

    # ==================== Game Spectating ====================

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
        if channel in self._spectate_connections:
            payload = json.dumps(message, default=str)
            dead: List[WebSocket] = []
            for ws in self._spectate_connections[channel]:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._spectate_connections[channel].remove(ws)

    # ==================== Connection Management ====================

    async def connect_spectator(
        self, channel: str, websocket: WebSocket
    ):
        """Accept and register a spectator WebSocket connection."""
        await websocket.accept()
        if channel not in self._spectate_connections:
            self._spectate_connections[channel] = []
        self._spectate_connections[channel].append(websocket)

    def disconnect_spectator(self, channel: str, websocket: WebSocket):
        """Remove a spectator WebSocket connection."""
        if channel in self._spectate_connections:
            self._spectate_connections[channel] = [
                ws
                for ws in self._spectate_connections[channel]
                if ws is not websocket
            ]
            if not self._spectate_connections[channel]:
                del self._spectate_connections[channel]

    # ==================== Replay ====================

    async def get_conversation_replay(
        self, conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a full conversation replay."""
        async with async_session() as db:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == UUID(conversation_id)
                )
            )
            conv = result.scalar_one_or_none()
            if not conv:
                return None
            return {
                "id": str(conv.id),
                "mode": conv.mode,
                "messages": conv.messages or [],
                "participants": conv.participants or [],
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
            }

    async def get_game_replay(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a full game replay."""
        async with async_session() as db:
            result = await db.execute(
                select(Game).where(Game.id == game_id)
            )
            game = result.scalar_one_or_none()
            if not game:
                return None
            return {
                "id": str(game.id),
                "game_type": game.game_type,
                "status": game.status,
                "config": game.config or {},
                "created_at": game.created_at.isoformat() if game.created_at else None,
            }


# Module-level singleton
spectator_service = SpectatorService()