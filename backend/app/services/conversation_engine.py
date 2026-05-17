import asyncio
import logging
from uuid import UUID
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.agent import Agent, AgentProfile
from app.models.conversation import Conversation, Message, ConversationMode, ConversationStatus
from app.models.model import Model, ModelCapability, CapabilityType
from app.services.llm_adapter import llm_adapter
from app.services.agent_service import AgentService
from app.services.evolution_service import evolution_service
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


class ConversationEngine:
    """Singleton conversation engine. DB sessions are obtained per-operation."""

    MAX_CONCURRENT = 10

    def __init__(self):
        self._running: Dict[str, bool] = {}
        self._cancelled: Dict[str, bool] = {}

    def cancel(self, conversation_id: UUID):
        """Request graceful cancellation of a running conversation."""
        key = str(conversation_id)
        if self._running.get(key, False):
            self._cancelled[key] = True

    async def start_conversation(self, db: AsyncSession, conversation_id: UUID, agent_ids: List[UUID]):
        # Check concurrent conversation limit
        if len(self._running) >= self.MAX_CONCURRENT:
            raise RuntimeError(
                f"Concurrent conversation limit reached ({self.MAX_CONCURRENT}). "
                "Please wait for an existing conversation to finish."
            )

        conversation = await db.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        conversation.status = ConversationStatus.ACTIVE
        db.add(conversation)
        await db.commit()

        key = str(conversation_id)
        self._running[key] = True
        self._cancelled[key] = False

        await ws_manager.broadcast_to_conversation(
            conversation_id, "conversation_started", {"conversation_id": str(conversation_id)}
        )

        participants = await self._load_participants(db, agent_ids)
        if not participants:
            logger.error("No participants loaded for conversation %s, aborting", conversation_id)
            await self._save_system_message(
                db, conversation_id,
                "No valid agents found. Conversation cannot start.", 0,
            )
            await self._finalize_conversation(conversation, [], 0)
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
                logger.warning("Agent %s not found, skipping", aid)
                continue
            result = await db.execute(
                select(AgentProfile).where(AgentProfile.agent_id == aid)
            )
            profile = result.scalar_one_or_none()

            # Check if the agent's model supports vision
            supports_vision = False
            model = await db.get(Model, agent.model_id)
            if not model:
                logger.warning("Model %s not found for agent %s", agent.model_id, agent.name)
            if model:
                cap_result = await db.execute(
                    select(ModelCapability)
                    .where(ModelCapability.model_id == model.id)
                    .where(ModelCapability.capability == CapabilityType.IMAGE_UNDERSTANDING)
                )
                supports_vision = cap_result.scalar_one_or_none() is not None

            participants.append({
                "agent": agent,
                "profile": profile,
                "supports_vision": supports_vision,
                "model_id": model.model_id if model else str(agent.model_id),
                "api_key": model.api_key if model else None,
                "api_base": model.api_base if model else None,
            })
        if not participants:
            logger.error("No valid participants found for agent_ids: %s", [str(a) for a in agent_ids])
        return participants

    def _build_messages_for_agent(
        self,
        system_prompt: str,
        history: List[Message],
        current_agent_id: UUID,
        supports_vision: bool = False,
    ) -> List[Dict[str, Any]]:
        """Build messages list for LLM, supporting both text-only and multimodal content."""
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            role = "assistant" if msg.agent_id == current_agent_id else "user"
            content = msg.content

            if isinstance(content, dict) and "blocks" in content:
                # Multimodal format: content has a "blocks" list
                parts: List[Dict[str, Any]] = []
                for block in content["blocks"]:
                    block_type = block.get("type", "text")
                    if block_type == "text":
                        parts.append({"type": "text", "text": block.get("text", "")})
                    elif block_type == "image" and supports_vision:
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": block.get("url", "")},
                        })
                    # Audio and other unsupported block types are skipped
                if parts:
                    messages.append({"role": role, "content": parts})
            else:
                # Simple text format (backward compatible): {"text": "..."}
                text = content.get("text", "") if isinstance(content, dict) else str(content)
                messages.append({"role": role, "content": text})
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

        agent = await db.get(Agent, agent_id)
        agent_name = agent.name if agent else "Unknown"

        await ws_manager.broadcast_to_conversation(conversation_id, "new_message", {
            "id": str(msg.id),
            "agent_id": str(agent_id),
            "agent_name": agent_name,
            "content": msg.content,
            "turn_number": turn,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })
        return msg

    async def _save_system_message(
        self, db: AsyncSession, conversation_id: UUID, text: str, turn: int
    ) -> Message:
        """Save a system message (e.g. cancellation notice) to the conversation."""
        msg = Message(
            conversation_id=conversation_id,
            agent_id=None,
            role="system",
            content={"text": text},
            turn_number=turn,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

        await ws_manager.broadcast_to_conversation(conversation_id, "new_message", {
            "id": str(msg.id),
            "agent_id": None,
            "agent_name": "System",
            "content": msg.content,
            "turn_number": turn,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })
        return msg

    async def _record_conversation_experiences(
        self,
        conversation: Conversation,
        participants: List[Dict[str, Any]],
        total_turns: int,
        cancelled: bool = False,
    ):
        """Record an experience for each participating agent after a conversation ends."""
        mode = conversation.mode if isinstance(conversation.mode, ConversationMode) else ConversationMode(conversation.mode)
        topic = conversation.title or conversation.config.get("topic", "")
        first_msg_text = ""
        if total_turns > 0:
            try:
                async with async_session() as db:
                    history = await self._get_history(db, conversation.id)
                    if history:
                        content = history[0].content
                        first_msg_text = content.get("text", "")[:100] if isinstance(content, dict) else ""
            except Exception:
                pass

        description_topic = topic or first_msg_text or "general"
        outcome = f"completed ({total_turns} turns)" if not cancelled else f"cancelled after {total_turns} turns"

        for i, p in enumerate(participants):
            agent = p["agent"]
            # First participant in debate/interview is considered a key contributor
            is_key = (mode == ConversationMode.DEBATE and i == 0) or \
                     (mode == ConversationMode.INTERVIEW and i == 0)
            decision = f"Participated in {mode.value} conversation about '{description_topic}'"
            if is_key:
                decision += " (key contributor)"

            try:
                async with async_session() as db:
                    await evolution_service.record_experience(
                        db=db,
                        agent_id=agent.id,
                        scene_type="conversation",
                        context_id=conversation.id,
                        decision=decision,
                        outcome=outcome,
                    )
            except Exception:
                # Don't let experience recording failure break the engine
                pass

    async def generate_reply(
        self,
        agent: Agent,
        profile: Optional[AgentProfile],
        messages: List[Dict[str, Any]],
        conversation_id: Optional[UUID] = None,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> str:
        if conversation_id:
            await ws_manager.broadcast_to_conversation(
                conversation_id, "agent_thinking", {"agent_id": str(agent.id)}
            )
        try:
            system_prompt = AgentService.build_system_prompt(agent, profile)
            full_messages = [{"role": "system", "content": system_prompt}] + messages
            result = await llm_adapter.chat(
                model_id=model_id or str(agent.model_id),
                messages=full_messages,
                api_key=api_key,
                api_base=api_base,
            )
            return result["content"]
        finally:
            if conversation_id:
                await ws_manager.broadcast_to_conversation(
                    conversation_id, "agent_done_thinking", {"agent_id": str(agent.id)}
                )

    async def handle_user_message(self, conversation_id: UUID):
        """After a user message is saved, trigger the next agent's response."""
        async with async_session() as db:
            conversation = await db.get(Conversation, conversation_id)
            if not conversation or conversation.status != ConversationStatus.ACTIVE:
                return

            agent_ids_str = conversation.config.get("agent_ids", [])
            if not agent_ids_str:
                return

            agent_ids = [UUID(aid) if isinstance(aid, str) else aid for aid in agent_ids_str]
            participants = await self._load_participants(db, agent_ids)
            if not participants:
                logger.warning("No valid participants for conversation %s", conversation_id)
                return

            history = await self._get_history(db, conversation_id)
            msg_count = len(history)
            mode = conversation.mode if isinstance(conversation.mode, ConversationMode) else ConversationMode(conversation.mode)
            topic = conversation.config.get("topic", conversation.title or "")

            # Determine next participant based on mode
            if mode == ConversationMode.INTERVIEW and len(participants) >= 2:
                if msg_count % 2 == 0:
                    next_p = participants[0]  # interviewer
                else:
                    idx = ((msg_count - 1) // 2) % max(1, len(participants) - 1)
                    next_p = participants[idx + 1]  # interviewee
            else:
                next_p = participants[msg_count % len(participants)]

            agent = next_p["agent"]
            profile = next_p["profile"]
            supports_vision = next_p.get("supports_vision", False)
            model_id = next_p.get("model_id")
            api_key = next_p.get("api_key")
            api_base = next_p.get("api_base")

            # Build messages for the agent
            system_prompt = AgentService.build_system_prompt(agent, profile)
            chat_messages = self._build_messages_for_agent(
                system_prompt, history, agent.id, supports_vision=supports_vision
            )
            chat_messages = [m for m in chat_messages if m["role"] != "system"]

            # Add mode-specific context
            if mode == ConversationMode.DEBATE:
                debate_topic = topic or "请就给定话题展开辩论"
                idx = participants.index(next_p)
                stance = "正方" if idx == 0 else "反方"
                chat_messages.insert(0, {
                    "role": "user",
                    "content": f"辩论主题：{debate_topic}。你是{stance}，请发表你的观点。",
                })
            elif mode == ConversationMode.INTERVIEW:
                interview_topic = topic or "请进行访谈"
                if msg_count == 0:
                    chat_messages.append({
                        "role": "user",
                        "content": f"访谈主题：{interview_topic}。请提出第一个问题。",
                    })
                elif msg_count % 2 == 1:
                    last_q = history[-1].content.get("text", "") if history else ""
                    chat_messages = [{"role": "user", "content": f"采访者问：{last_q}\n请回答。"}]

            # Generate response
            try:
                reply = await self.generate_reply(agent, profile, chat_messages, conversation_id, model_id=model_id, api_key=api_key, api_base=api_base)
                await self._save_message(db, conversation_id, agent.id, reply, msg_count)
            except Exception as e:
                logger.error("Agent %s failed to respond to user message: %s", agent.name, e)
                await self._save_system_message(
                    db, conversation_id,
                    f"Agent {agent.name} failed to respond: {str(e)[:200]}",
                    msg_count,
                )

    def _should_continue(self, key: str, turn: int, max_turns: int) -> bool:
        """Check if the conversation loop should continue."""
        return self._running.get(key, False) and not self._cancelled.get(key, False) and turn < max_turns

    async def _finalize_conversation(
        self,
        conversation: Conversation,
        participants: List[Dict[str, Any]],
        total_turns: int,
    ):
        """Clean up running state and finalize a conversation."""
        key = str(conversation.id)
        cancelled = self._cancelled.get(key, False)

        if cancelled:
            # Save cancellation system message
            async with async_session() as db:
                await self._save_system_message(
                    db, conversation.id,
                    "This conversation has been cancelled.",
                    total_turns,
                )

        # Record experiences for all participants
        await self._record_conversation_experiences(
            conversation, participants, total_turns, cancelled=cancelled
        )

        # Update conversation status
        async with async_session() as db:
            conv = await db.get(Conversation, conversation.id)
            if conv:
                conv.status = ConversationStatus.ENDED
                await db.commit()

        # Clean up state dicts
        self._running.pop(key, None)
        self._cancelled.pop(key, None)

        await ws_manager.broadcast_to_conversation(
            conversation.id, "conversation_ended", {"conversation_id": str(conversation.id)}
        )

    async def _run_free_mode(
        self, conversation: Conversation, participants: List[Dict[str, Any]]
    ):
        turn = 0
        max_turns = conversation.config.get("max_turns", 10)
        key = str(conversation.id)

        while self._should_continue(key, turn, max_turns):
            current = participants[turn % len(participants)]
            agent = current["agent"]
            profile = current["profile"]
            supports_vision = current.get("supports_vision", False)
            model_id = current.get("model_id")
            api_key = current.get("api_key")
            api_base = current.get("api_base")

            # Use a new session for each iteration
            async with async_session() as db:
                history = await self._get_history(db, conversation.id)
                chat_messages = self._build_messages_for_agent(
                    AgentService.build_system_prompt(agent, profile), history, agent.id,
                    supports_vision=supports_vision,
                )
                chat_messages = [m for m in chat_messages if m["role"] != "system"]

                try:
                    reply = await self.generate_reply(agent, profile, chat_messages, conversation.id, model_id=model_id, api_key=api_key, api_base=api_base)
                    await self._save_message(db, conversation.id, agent.id, reply, turn)
                except Exception as e:
                    logger.error("Agent %s failed on turn %d: %s", agent.name, turn, e)
                    await self._save_system_message(
                        db, conversation.id,
                        f"Agent {agent.name} failed to respond: {str(e)[:200]}",
                        turn,
                    )
            turn += 1
            await asyncio.sleep(1.0)

        await self._finalize_conversation(conversation, participants, turn)

    async def _run_debate_mode(
        self, conversation: Conversation, participants: List[Dict[str, Any]]
    ):
        if len(participants) < 2:
            return
        turn = 0
        max_turns = conversation.config.get("max_turns", 10)
        topic = conversation.config.get("topic", conversation.title or "请就给定话题展开辩论")
        key = str(conversation.id)

        while self._should_continue(key, turn, max_turns):
            idx = turn % len(participants)
            current = participants[idx]
            agent = current["agent"]
            profile = current["profile"]
            supports_vision = current.get("supports_vision", False)
            model_id = current.get("model_id")
            api_key = current.get("api_key")
            api_base = current.get("api_base")
            stance = "正方" if idx == 0 else "反方"

            async with async_session() as db:
                history = await self._get_history(db, conversation.id)
                chat_messages = self._build_messages_for_agent(
                    AgentService.build_system_prompt(agent, profile), history, agent.id,
                    supports_vision=supports_vision,
                )
                chat_messages = [m for m in chat_messages if m["role"] != "system"]
                chat_messages.insert(0, {
                    "role": "user",
                    "content": f"辩论主题：{topic}。你是{stance}，请发表你的观点。",
                })

                try:
                    reply = await self.generate_reply(agent, profile, chat_messages, conversation.id, model_id=model_id, api_key=api_key, api_base=api_base)
                    await self._save_message(db, conversation.id, agent.id, reply, turn)
                except Exception as e:
                    logger.error("Agent %s failed on turn %d: %s", agent.name, turn, e)
                    await self._save_system_message(
                        db, conversation.id,
                        f"Agent {agent.name} failed to respond: {str(e)[:200]}",
                        turn,
                    )
            turn += 1
            await asyncio.sleep(1.0)

        await self._finalize_conversation(conversation, participants, turn)

    async def _run_relay_mode(
        self, conversation: Conversation, participants: List[Dict[str, Any]]
    ):
        turn = 0
        max_turns = conversation.config.get("max_turns", len(participants) * 2)
        key = str(conversation.id)

        while self._should_continue(key, turn, max_turns):
            current = participants[turn % len(participants)]
            agent = current["agent"]
            profile = current["profile"]
            model_id = current.get("model_id")
            api_key = current.get("api_key")
            api_base = current.get("api_base")

            async with async_session() as db:
                history = await self._get_history(db, conversation.id)
                if not history:
                    prompt = conversation.config.get("initial_prompt", "请开始你的发言。")
                    chat_messages = [{"role": "user", "content": prompt}]
                else:
                    last_msg = history[-1]
                    chat_messages = [{"role": "user", "content": f"上一位发言者说：{last_msg.content.get('text', '')}"}]

                try:
                    reply = await self.generate_reply(agent, profile, chat_messages, conversation.id, model_id=model_id, api_key=api_key, api_base=api_base)
                    await self._save_message(db, conversation.id, agent.id, reply, turn)
                except Exception as e:
                    logger.error("Agent %s failed on turn %d: %s", agent.name, turn, e)
                    await self._save_system_message(
                        db, conversation.id,
                        f"Agent {agent.name} failed to respond: {str(e)[:200]}",
                        turn,
                    )
            turn += 1
            await asyncio.sleep(1.0)

        await self._finalize_conversation(conversation, participants, turn)

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
        key = str(conversation.id)

        while self._should_continue(key, turn, max_turns):
            async with async_session() as db:
                try:
                    if turn % 2 == 0:
                        agent = interviewer["agent"]
                        profile = interviewer["profile"]
                        supports_vision = interviewer.get("supports_vision", False)
                        model_id = interviewer.get("model_id")
                        api_key = interviewer.get("api_key")
                        api_base = interviewer.get("api_base")
                        history = await self._get_history(db, conversation.id)
                        chat_messages = self._build_messages_for_agent(
                            AgentService.build_system_prompt(agent, profile), history, agent.id,
                            supports_vision=supports_vision,
                        )
                        chat_messages = [m for m in chat_messages if m["role"] != "system"]
                        if turn == 0:
                            chat_messages.append({"role": "user", "content": f"访谈主题：{topic}。请提出第一个问题。"})
                        reply = await self.generate_reply(agent, profile, chat_messages, conversation.id, model_id=model_id, api_key=api_key, api_base=api_base)
                    else:
                        target = interviewees[(turn // 2) % len(interviewees)]
                        agent = target["agent"]
                        profile = target["profile"]
                        model_id = target.get("model_id")
                        api_key = target.get("api_key")
                        api_base = target.get("api_base")
                        history = await self._get_history(db, conversation.id)
                        last_q = history[-1].content.get("text", "") if history else ""
                        chat_messages = [{"role": "user", "content": f"采访者问：{last_q}\n请回答。"}]
                        reply = await self.generate_reply(agent, profile, chat_messages, conversation.id, model_id=model_id, api_key=api_key, api_base=api_base)

                    await self._save_message(db, conversation.id, agent.id, reply, turn)
                except Exception as e:
                    logger.error("Agent %s failed on turn %d: %s", agent.name, turn, e)
                    await self._save_system_message(
                        db, conversation.id,
                        f"Agent {agent.name} failed to respond: {str(e)[:200]}",
                        turn,
                    )
            turn += 1
            await asyncio.sleep(1.0)

        await self._finalize_conversation(conversation, participants, turn)

    def pause(self, conversation_id: UUID):
        self._running[str(conversation_id)] = False

    def resume(self, conversation_id: UUID):
        self._running[str(conversation_id)] = True
