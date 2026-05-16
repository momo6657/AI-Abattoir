import asyncio
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.conversation import ConversationCreate, ConversationResponse, MessageResponse
from app.services.conversation_engine import ConversationEngine
from app.services.message_router import MessageRouter
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/conversations", tags=["conversations"])


class StartConversationRequest(BaseModel):
    agent_ids: List[UUID]


class SendMessageRequest(BaseModel):
    content: str
    agent_id: Optional[UUID] = None


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).order_by(Conversation.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=ConversationResponse)
async def create_conversation(data: ConversationCreate, db: AsyncSession = Depends(get_db)):
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
):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    engine = ConversationEngine(db)
    asyncio.create_task(engine.start_conversation(conversation_id, body.agent_ids))
    return {"status": "started", "conversation_id": str(conversation_id)}


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
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
async def pause_conversation(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    engine = ConversationEngine(db)
    engine.pause(conversation_id)

    conversation.status = "paused"
    await db.commit()
    await ws_manager.broadcast(conversation_id, {"type": "conversation_paused"})
    return {"status": "paused", "conversation_id": str(conversation_id)}


@router.post("/{conversation_id}/resume")
async def resume_conversation(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    engine = ConversationEngine(db)
    engine.resume(conversation_id)

    conversation.status = "active"
    await db.commit()
    await ws_manager.broadcast(conversation_id, {"type": "conversation_resumed"})
    return {"status": "resumed", "conversation_id": str(conversation_id)}
