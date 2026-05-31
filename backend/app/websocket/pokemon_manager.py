"""
WebSocket manager for Pokemon battles
Handles real-time battle state updates and client communication
"""

import json
import logging
from typing import Dict, Set, Optional, Any
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect

from app.services.pokemon.battle_engine import BattleEngine, BattleState
from app.services.pokemon.ai_decision import AIDecisionEngine

logger = logging.getLogger(__name__)


class BattleConnection:
    """Manages WebSocket connections for a single battle"""

    def __init__(self, battle_id: str):
        self.battle_id = battle_id
        self.active_connections: Dict[str, WebSocket] = {}  # client_id -> websocket
        self.client_roles: Dict[str, str] = {}  # client_id -> "player1" | "player2" | "spectator"
        self.battle_state: Optional[BattleState] = None
        self.engine = BattleEngine()
        self.ai_engine = AIDecisionEngine()
        self.pending_actions: Dict[str, list] = {}  # "player1" -> actions, "player2" -> actions

    async def connect(self, websocket: WebSocket, client_id: str, role: str = "spectator"):
        """Accept and register a new connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_roles[client_id] = role
        logger.info(f"Client {client_id} connected to battle {self.battle_id} as {role}")

    def disconnect(self, client_id: str):
        """Remove a connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.client_roles:
            del self.client_roles[client_id]
        logger.info(f"Client {client_id} disconnected from battle {self.battle_id}")

    async def broadcast(self, message: Dict[str, Any]):
        """Send message to all connected clients"""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to {client_id}: {e}")
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    async def send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send message to a specific client"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to {client_id}: {e}")
                self.disconnect(client_id)

    async def handle_message(self, client_id: str, data: Dict[str, Any]):
        """Handle incoming message from a client"""
        message_type = data.get("type")
        role = self.client_roles.get(client_id, "spectator")

        if message_type == "action":
            if role not in ["player1", "player2"]:
                await self.send_to_client(client_id, {
                    "type": "error",
                    "message": "Only players can submit actions"
                })
                return

            self.pending_actions[role] = data.get("actions", [])
            logger.info(f"Received actions from {role}")

            # Check if both players have submitted actions
            if "player1" in self.pending_actions and "player2" in self.pending_actions:
                await self._execute_turn()

        elif message_type == "get_state":
            if self.battle_state:
                await self.send_to_client(client_id, {
                    "type": "state",
                    "state": self.battle_state.to_dict()
                })

        elif message_type == "chat":
            await self.broadcast({
                "type": "chat",
                "client_id": client_id,
                "role": role,
                "message": data.get("message", "")
            })

    async def _execute_turn(self):
        """Execute a turn when both players have submitted actions"""
        if not self.battle_state:
            return

        p1_actions = self.pending_actions.get("player1", [])
        p2_actions = self.pending_actions.get("player2", [])

        # Execute turn
        self.battle_state = self.engine.execute_turn(
            self.battle_state,
            p1_actions,
            p2_actions
        )

        # Clear pending actions
        self.pending_actions = {}

        # Broadcast updated state
        await self.broadcast({
            "type": "turn_complete",
            "turn": self.battle_state.turn,
            "state": self.battle_state.to_dict(),
            "log": self.battle_state.battle_log[-5:]  # Last 5 log entries
        })

        # Check if battle is over
        if self.battle_state.is_over():
            await self.broadcast({
                "type": "battle_end",
                "winner": self.battle_state.winner,
                "state": self.battle_state.to_dict()
            })


class PokemonWebSocketManager:
    """Global manager for all Pokemon battle WebSocket connections"""

    def __init__(self):
        self.battles: Dict[str, BattleConnection] = {}

    def get_or_create_battle(self, battle_id: str) -> BattleConnection:
        """Get or create a battle connection manager"""
        if battle_id not in self.battles:
            self.battles[battle_id] = BattleConnection(battle_id)
        return self.battles[battle_id]

    def remove_battle(self, battle_id: str):
        """Remove a battle connection manager"""
        if battle_id in self.battles:
            del self.battles[battle_id]

    async def connect(self, battle_id: str, websocket: WebSocket, client_id: str, role: str = "spectator"):
        """Connect a client to a battle"""
        battle = self.get_or_create_battle(battle_id)
        await battle.connect(websocket, client_id, role)

    def disconnect(self, battle_id: str, client_id: str):
        """Disconnect a client from a battle"""
        if battle_id in self.battles:
            self.battles[battle_id].disconnect(client_id)

    async def handle_message(self, battle_id: str, client_id: str, data: Dict[str, Any]):
        """Handle a message from a client"""
        if battle_id in self.battles:
            await self.battles[battle_id].handle_message(client_id, data)


# Global instance
pokemon_ws_manager = PokemonWebSocketManager()
