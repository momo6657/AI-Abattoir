from uuid import UUID
from typing import Optional, Dict, Any, List, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message, ConversationMode
from app.models.agent import Agent
from app.websocket.manager import ws_manager


class MessageRouter:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def handle_incoming_message(
        self, conversation_id: UUID, agent_id: Optional[UUID], content: str
    ) -> Message:
        conversation = await self.db.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.turn_number.desc())
            .limit(1)
        )
        last_msg = result.scalar_one_or_none()
        next_turn = (last_msg.turn_number + 1) if last_msg and last_msg.turn_number is not None else 0

        message = Message(
            conversation_id=conversation_id,
            agent_id=agent_id,
            role="user" if agent_id is None else "assistant",
            content={"text": content},
            turn_number=next_turn,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        visible_to = await self.determine_visibility(conversation_id, message)
        if visible_to is not None:
            await self.broadcast_to_participants(conversation_id, message, visible_to=visible_to)

        return message

    async def broadcast_to_participants(
        self,
        conversation_id: UUID,
        message: Message,
        visible_to: Optional[set] = None,
    ):
        payload = {
            "type": "message",
            "data": {
                "id": str(message.id),
                "agent_id": str(message.agent_id) if message.agent_id else None,
                "role": message.role,
                "content": message.content,
                "turn_number": message.turn_number,
            },
        }
        if visible_to is not None:
            payload["data"]["visible_to"] = list(visible_to)
        await ws_manager.broadcast(conversation_id, payload)

    async def determine_visibility(
        self, conversation_id: UUID, message: Message
    ) -> Optional[set]:
        """Return None if invisible, empty set if visible to all, or a set of agent IDs."""
        conversation = await self.db.get(Conversation, conversation_id)
        if not conversation:
            return None

        mode = conversation.mode if isinstance(conversation.mode, ConversationMode) else ConversationMode(conversation.mode)

        if mode in (ConversationMode.FREE, ConversationMode.DEBATE, ConversationMode.INTERVIEW):
            return set()  # visible to all

        if mode == ConversationMode.RELAY:
            history_result = await self.db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.turn_number)
            )
            history = list(history_result.scalars().all())
            if len(history) <= 1:
                return set()  # first message: visible to all
            agent_ids = conversation.config.get("agent_ids", [])
            if not agent_ids:
                return set()
            current_turn = len(history) - 1
            current_agent_idx = current_turn % len(agent_ids)
            visible_to = {str(agent_ids[current_agent_idx])}
            if current_agent_idx > 0:
                visible_to.add(str(agent_ids[current_agent_idx - 1]))
            return visible_to

        return set()  # default: visible to all
