import asyncio
import logging
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db, async_session
from app.models.conversation import Conversation, Message, ConversationMode, ConversationStatus
from app.models.user import User
from app.schemas.conversation import ConversationCreate, ConversationResponse, MessageResponse
from app.services.conversation_engine import ConversationEngine
from app.services.message_router import MessageRouter
from app.websocket.manager import ws_manager
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Module-level singleton: all pause/resume/start operations share the same engine instance
_engine = ConversationEngine._create_singleton()


class StartConversationRequest(BaseModel):
    agent_ids: List[UUID]


class SendMessageRequest(BaseModel):
    content: str
    agent_id: Optional[UUID] = None


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .order_by(Conversation.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/", response_model=ConversationResponse)
async def create_conversation(data: ConversationCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Validate mode
    valid_modes = {m.value for m in ConversationMode}
    if data.mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode '{data.mode}'. Must be one of: {', '.join(sorted(valid_modes))}")

    # Validate agent_ids for non-free modes
    if data.mode != ConversationMode.FREE.value:
        if len(data.agent_ids) < 2:
            raise HTTPException(status_code=400, detail=f"Mode '{data.mode}' requires at least 2 agents")
        if data.mode == ConversationMode.DEBATE.value and len(data.agent_ids) != 2:
            raise HTTPException(status_code=400, detail="Debate mode requires exactly 2 agents")

    conversation = Conversation(
        title=data.title,
        mode=data.mode,
        config={**data.config, "agent_ids": [str(aid) for aid in data.agent_ids]},
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.post("/{conversation_id}/start")
async def start_conversation(
    conversation_id: UUID,
    body: StartConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def _run_and_log():
        try:
            async with async_session() as session:
                await _engine.start_conversation(session, conversation_id, body.agent_ids)
        except Exception:
            logger.exception("Conversation %s failed to start", conversation_id)

    asyncio.create_task(_run_and_log())
    return {"status": "started", "conversation_id": str(conversation_id)}


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    router_instance = MessageRouter(db)
    message = await router_instance.handle_incoming_message(
        conversation_id, body.agent_id, body.content
    )
    return message


@router.post("/{conversation_id}/pause")
async def pause_conversation(conversation_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    _engine.pause(conversation_id)

    conversation.status = ConversationStatus.PAUSED
    await db.commit()
    await ws_manager.broadcast(conversation_id, {"type": "conversation_paused"})
    return {"status": "paused", "conversation_id": str(conversation_id)}


@router.post("/{conversation_id}/resume")
async def resume_conversation(conversation_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    _engine.resume(conversation_id)

    conversation.status = ConversationStatus.ACTIVE
    await db.commit()
    await ws_manager.broadcast(conversation_id, {"type": "conversation_resumed"})
    return {"status": "resumed", "conversation_id": str(conversation_id)}


@router.post("/{conversation_id}/end")
async def end_conversation(conversation_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    _engine.cancel(conversation_id)

    conversation.status = ConversationStatus.ENDED
    await db.commit()
    await ws_manager.broadcast(conversation_id, {"type": "conversation_ended"})
    return {"status": "ended", "conversation_id": str(conversation_id)}
