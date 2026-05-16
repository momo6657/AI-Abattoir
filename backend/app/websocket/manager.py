import json
import logging
from uuid import UUID
from typing import Dict, List, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
        self._agent_info: Dict[str, Dict[str, str]] = {}  # ws id -> {agent_id, agent_name}

    async def connect(self, websocket: WebSocket, conversation_id: UUID):
        await websocket.accept()
        key = str(conversation_id)
        if key not in self._connections:
            self._connections[key] = []
        self._connections[key].append(websocket)

    def disconnect(self, websocket: WebSocket, conversation_id: UUID):
        key = str(conversation_id)
        ws_id = id(websocket)
        self._agent_info.pop(ws_id, None)
        if key in self._connections:
            self._connections[key] = [
                ws for ws in self._connections[key] if ws is not websocket
            ]
            if not self._connections[key]:
                del self._connections[key]

    def set_agent_info(self, websocket: WebSocket, agent_id: str, agent_name: str = ""):
        self._agent_info[id(websocket)] = {"agent_id": agent_id, "agent_name": agent_name}

    async def broadcast(self, conversation_id: UUID, data: dict):
        key = str(conversation_id)
        if key not in self._connections:
            return
        payload = json.dumps(data, default=str)
        dead: List[WebSocket] = []
        for ws in self._connections.get(key, []):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[key].remove(ws)
        if dead:
            logger.debug("Removed %d dead connections for conversation %s", len(dead), key)

    async def broadcast_to_conversation(
        self, conversation_id, event_type: str, data: dict
    ):
        """Send a typed event to all clients watching a conversation.

        *conversation_id* may be a UUID or a string.
        """
        cid = UUID(str(conversation_id)) if not isinstance(conversation_id, UUID) else conversation_id
        await self.broadcast(cid, {"type": event_type, "data": data})

    def get_connection_count(self, conversation_id: UUID) -> int:
        key = str(conversation_id)
        return len(self._connections.get(key, []))


ws_manager = ConnectionManager()
