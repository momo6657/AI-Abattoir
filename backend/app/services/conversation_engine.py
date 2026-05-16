import asyncio
import random
from uuid import UUID
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.agent import Agent, AgentProfile
from app.models.conversation import Conversation, Message, ConversationMode, ConversationStatus
from app.services.llm_adapter import llm_adapter
from app.services.agent_service import AgentService
from app.websocket.manager import ws_manager


class ConversationEngine:
    """Singleton conversation engine. DB sessions are obtained per-operation."""

    def __init__(self):
        self._running: Dict[str, bool] = {}

    @classmethod
    def _create_singleton(cls) -> "ConversationEngine":
        return cls()

    async def start_conversation(self, db: AsyncSession, conversation_id: UUID, agent_ids: List[UUID]):
        conversation = await db.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        conversation.status = ConversationStatus.ACTIVE
        db.add(conversation)
        await db.commit()

        key = str(conversation_id)
        self._running[key] = True

        participants = await self._load_participants(db, agent_ids)
        if not participants:
            return

        mode = conversation.mode if isinstance(conversation.mode, ConversationMode) else ConversationMode(conversation.mode)
        if mode == ConversationMode.FREE:
            await self._run_free_mode(conversation, participants)
        elif mode == ConversationMode.DEBATE:
            await self._run_debate_mode(conversation, participants)
        elif mode == ConversationMode.RELAY:
            await self._run_relay_mode(conversation, participants)
        elif mode == ConversationMode.INTERVIEW:
            await self._run_interview_mode(conversation, participants)

    async def _load_participants(self, db: AsyncSession, agent_ids: List[UUID]) -> List[Dict[str, Any]]:
        participants = []
        for aid in agent_ids:
            agent = await db.get(Agent, aid)
            if not agent:
                continue
            result = await db.execute(
                select(AgentProfile).where(AgentProfile.agent_id == aid)
            )
            profile = result.scalar_one_or_none()
            participants.append({"agent": agent, "profile": profile})
        return participants

    def _build_messages_for_agent(
        self, system_prompt: str, history: List[Message], current_agent_id: UUID
    ) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            if msg.agent_id == current_agent_id:
                messages.append({"role": "assistant", "content": msg.content.get("text", "")})
            else:
                messages.append({"role": "user", "content": msg.content.get("text", "")})
        return messages

    async def _get_history(self, db: AsyncSession, conversation_id: UUID) -> List[Message]:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.turn_number)
        )
        return list(result.scalars().all())

    async def _save_message(
        self, db: AsyncSession, conversation_id: UUID, agent_id: UUID, text: str, turn: int
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            agent_id=agent_id,
            role="assistant",
            content={"text": text},
            turn_number=turn,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

        await ws_manager.broadcast(conversation_id, {
            "type": "message",
            "data": {
                "id": str(msg.id),
                "agent_id": str(agent_id),
                "content": msg.content,
                "turn_number": turn,
            },
        })
        return msg

    async def generate_reply(
        self, agent: Agent, profile: Optional[AgentProfile], messages: List[Dict[str, str]]
    ) -> str:
        agent_service = AgentService.__new__(AgentService)
        system_prompt = agent_service.build_system_prompt(agent, profile)
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        result = await llm_adapter.chat(
            model_id=str(agent.model_id),
            messages=full_messages,
        )
        return result["content"]

    async def _run_free_mode(
        self, conversation: Conversation, participants: List[Dict[str, Any]]
    ):
        turn = 0
        max_turns = conversation.config.get("max_turns", 10)
        while self._running.get(str(conversation.id), False) and turn < max_turns:
            current = participants[turn % len(participants)]
            agent = current["agent"]
            profile = current["profile"]

            # Use a new session for each iteration
            async with async_session() as db:
                history = await self._get_history(db, conversation.id)
                agent_service = AgentService(db)
                chat_messages = self._build_messages_for_agent(
                    agent_service.build_system_prompt(agent, profile), history, agent.id
                )
                chat_messages = [m for m in chat_messages if m["role"] != "system"]

                reply = await self.generate_reply(agent, profile, chat_messages)
                await self._save_message(db, conversation.id, agent.id, reply, turn)
            turn += 1
            await asyncio.sleep(0.5)

        # Final status update with its own session
        async with async_session() as db:
            conv = await db.get(Conversation, conversation.id)
            if conv:
                conv.status = ConversationStatus.ENDED
                await db.commit()
        await ws_manager.broadcast(conversation.id, {"type": "conversation_ended"})

    async def _run_debate_mode(
        self, conversation: Conversation, participants: List[Dict[str, Any]]
    ):
        if len(participants) < 2:
            return
        turn = 0
        max_turns = conversation.config.get("max_turns", 10)
        topic = conversation.config.get("topic", conversation.title or "请就给定话题展开辩论")

        while self._running.get(str(conversation.id), False) and turn < max_turns:
            idx = turn % len(participants)
            current = participants[idx]
            agent = current["agent"]
            profile = current["profile"]
            stance = "正方" if idx == 0 else "反方"

            async with async_session() as db:
                history = await self._get_history(db, conversation.id)
                agent_service = AgentService(db)
                chat_messages = self._build_messages_for_agent(
                    agent_service.build_system_prompt(agent, profile), history, agent.id
                )
                chat_messages = [m for m in chat_messages if m["role"] != "system"]
                chat_messages.insert(0, {
                    "role": "user",
                    "content": f"辩论主题：{topic}。你是{stance}，请发表你的观点。",
                })

                reply = await self.generate_reply(agent, profile, chat_messages)
                await self._save_message(db, conversation.id, agent.id, reply, turn)
            turn += 1
            await asyncio.sleep(0.5)

        async with async_session() as db:
            conv = await db.get(Conversation, conversation.id)
            if conv:
                conv.status = ConversationStatus.ENDED
                await db.commit()
        await ws_manager.broadcast(conversation.id, {"type": "conversation_ended"})

    async def _run_relay_mode(
        self, conversation: Conversation, participants: List[Dict[str, Any]]
    ):
        turn = 0
        max_turns = conversation.config.get("max_turns", len(participants) * 2)

        while self._running.get(str(conversation.id), False) and turn < max_turns:
            current = participants[turn % len(participants)]
            agent = current["agent"]
            profile = current["profile"]

            async with async_session() as db:
                history = await self._get_history(db, conversation.id)
                if not history:
                    prompt = conversation.config.get("initial_prompt", "请开始你的发言。")
                    chat_messages = [{"role": "user", "content": prompt}]
                else:
                    last_msg = history[-1]
                    chat_messages = [{"role": "user", "content": f"上一位发言者说：{last_msg.content.get('text', '')}"}]

                reply = await self.generate_reply(agent, profile, chat_messages)
                await self._save_message(db, conversation.id, agent.id, reply, turn)
            turn += 1
            await asyncio.sleep(0.5)

        async with async_session() as db:
            conv = await db.get(Conversation, conversation.id)
            if conv:
                conv.status = ConversationStatus.ENDED
                await db.commit()
        await ws_manager.broadcast(conversation.id, {"type": "conversation_ended"})

    async def _run_interview_mode(
        self, conversation: Conversation, participants: List[Dict[str, Any]]
    ):
        if len(participants) < 2:
            return

        interviewer = participants[0]
        interviewees = participants[1:]
        turn = 0
        max_turns = conversation.config.get("max_turns", 10)
        topic = conversation.config.get("topic", conversation.title or "请进行访谈")

        while self._running.get(str(conversation.id), False) and turn < max_turns:
            async with async_session() as db:
                if turn % 2 == 0:
                    agent = interviewer["agent"]
                    profile = interviewer["profile"]
                    history = await self._get_history(db, conversation.id)
                    agent_service = AgentService(db)
                    chat_messages = self._build_messages_for_agent(
                        agent_service.build_system_prompt(agent, profile), history, agent.id
                    )
                    chat_messages = [m for m in chat_messages if m["role"] != "system"]
                    if turn == 0:
                        chat_messages.append({"role": "user", "content": f"访谈主题：{topic}。请提出第一个问题。"})
                    reply = await self.generate_reply(agent, profile, chat_messages)
                else:
                    target = interviewees[(turn // 2) % len(interviewees)]
                    agent = target["agent"]
                    profile = target["profile"]
                    history = await self._get_history(db, conversation.id)
                    last_q = history[-1].content.get("text", "") if history else ""
                    chat_messages = [{"role": "user", "content": f"采访者问：{last_q}\n请回答。"}]
                    reply = await self.generate_reply(agent, profile, chat_messages)

                await self._save_message(db, conversation.id, agent.id, reply, turn)
            turn += 1
            await asyncio.sleep(0.5)

        async with async_session() as db:
            conv = await db.get(Conversation, conversation.id)
            if conv:
                conv.status = ConversationStatus.ENDED
                await db.commit()
        await ws_manager.broadcast(conversation.id, {"type": "conversation_ended"})

    async def route_message(self, db: AsyncSession, conversation_id: UUID, message: Message) -> Optional[UUID]:
        conversation = await db.get(Conversation, conversation_id)
        if not conversation:
            return None
        return await self.get_next_agent(db, conversation_id)

    async def get_next_agent(self, db: AsyncSession, conversation_id: UUID) -> Optional[UUID]:
        conversation = await db.get(Conversation, conversation_id)
        if not conversation:
            return None

        history = await self._get_history(db, conversation_id)
        mode = conversation.mode if isinstance(conversation.mode, ConversationMode) else ConversationMode(conversation.mode)

        agent_ids = conversation.config.get("agent_ids", [])
        if not agent_ids:
            return None

        if mode == ConversationMode.FREE:
            return agent_ids[len(history) % len(agent_ids)]
        elif mode == ConversationMode.DEBATE:
            return agent_ids[len(history) % len(agent_ids)]
        elif mode == ConversationMode.RELAY:
            return agent_ids[len(history) % len(agent_ids)]
        elif mode == ConversationMode.INTERVIEW:
            if len(history) % 2 == 0:
                return agent_ids[0]
            else:
                idx = 1 + ((len(history) // 2) - 1) % (len(agent_ids) - 1)
                return agent_ids[idx] if idx < len(agent_ids) else agent_ids[1]
        return None

    async def build_context(self, db: AsyncSession, conversation_id: UUID, agent_id: UUID) -> List[Dict[str, str]]:
        agent = await db.get(Agent, agent_id)
        if not agent:
            return []

        result = await db.execute(
            select(AgentProfile).where(AgentProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        agent_service = AgentService(db)
        system_prompt = agent_service.build_system_prompt(agent, profile)

        history = await self._get_history(db, conversation_id)
        messages = self._build_messages_for_agent(system_prompt, history, agent_id)
        return messages

    def pause(self, conversation_id: UUID):
        self._running[str(conversation_id)] = False

    def resume(self, conversation_id: UUID):
        self._running[str(conversation_id)] = True
