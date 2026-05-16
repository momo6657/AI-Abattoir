import json
from uuid import UUID
from typing import Dict, List, Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: UUID):
        await websocket.accept()
        key = str(conversation_id)
        if key not in self._connections:
            self._connections[key] = []
        self._connections[key].append(websocket)

    def disconnect(self, websocket: WebSocket, conversation_id: UUID):
        key = str(conversation_id)
        if key in self._connections:
            self._connections[key] = [
                ws for ws in self._connections[key] if ws is not websocket
            ]
            if not self._connections[key]:
                del self._connections[key]

    async def broadcast(self, conversation_id: UUID, data: dict):
        key = str(conversation_id)
        if key not in self._connections:
            return
        payload = json.dumps(data, default=str)
        dead: List[WebSocket] = []
        for ws in self._connections[key]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[key].remove(ws)

    def get_connection_count(self, conversation_id: UUID) -> int:
        key = str(conversation_id)
        return len(self._connections.get(key, []))


ws_manager = ConnectionManager()
