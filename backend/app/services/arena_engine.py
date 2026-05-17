import base64
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.arena import ArenaMatch, ArenaParticipant, ArenaVote, MatchType, MatchStatus
from app.models.agent import Agent, AgentProfile
from app.models.model import Model
from app.services.llm_adapter import llm_adapter
from app.services.image_adapter import image_adapter
from app.services.tts_adapter import tts_adapter
from app.services.agent_service import AgentService
from app.services.media_storage import media_storage

logger = logging.getLogger(__name__)


class ArenaEngine:
    """竞技场引擎，支持多种 AI 对抗模式"""

    async def create_match(
        self,
        db: AsyncSession,
        match_type: str,
        prompt: str,
        agent_ids: List[str],
        config: Optional[dict] = None,
        title: Optional[str] = None,
        creator_id: Optional[str] = None,
    ) -> ArenaMatch:
        match = ArenaMatch(
            match_type=match_type,
            title=title or f"{match_type} Arena Match",
            prompt=prompt,
            config=config or {},
            creator_id=creator_id,
        )
        db.add(match)
        await db.flush()

        for agent_id in agent_ids:
            participant = ArenaParticipant(
                match_id=match.id,
                agent_id=agent_id,
            )
            db.add(participant)

        await db.commit()
        await db.refresh(match)
        return match

    async def start_match(self, db: AsyncSession, match_id: str) -> ArenaMatch:
        match = await db.get(ArenaMatch, match_id)
        if not match:
            raise ValueError("Match not found")
        if match.status != MatchStatus.WAITING:
            raise ValueError(f"Match is already {match.status}")

        match.status = MatchStatus.IN_PROGRESS
        await db.flush()

        result = await db.execute(
            select(ArenaParticipant).where(ArenaParticipant.match_id == match.id)
        )
        participants = result.scalars().all()

        for participant in participants:
            agent = await db.get(Agent, participant.agent_id)
            if not agent:
                logger.warning("Agent %s not found, skipping", participant.agent_id)
                continue

            model = await db.get(Model, agent.model_id)
            if not model:
                logger.warning("Model %s not found for agent %s", agent.model_id, agent.id)
                continue

            profile_result = await db.execute(
                select(AgentProfile).where(AgentProfile.agent_id == agent.id)
            )
            profile = profile_result.scalar_one_or_none()

            try:
                if match.match_type in (MatchType.QA_PK, MatchType.CREATIVE, MatchType.REASONING, MatchType.CODE):
                    response_content = await self._generate_text_response(
                        db, match, agent, profile, model
                    )
                elif match.match_type == MatchType.IMAGE_GEN:
                    response_content = await self._generate_image_response(
                        db, match, agent, profile, model
                    )
                elif match.match_type == MatchType.VOICE:
                    response_content = await self._generate_voice_response(
                        db, match, agent, profile, model
                    )
                else:
                    response_content = {"error": f"Unsupported match type: {match.match_type}"}

                participant.response_content = response_content
            except Exception as e:
                logger.exception(
                    "Failed to generate response for agent=%s in match=%s (type=%s)",
                    agent.id, match.id, match.match_type,
                )
                participant.response_content = {
                    "type": match.match_type.value if hasattr(match.match_type, 'value') else str(match.match_type),
                    "error": f"Generation failed: {str(e)[:300]}",
                }

        match.status = MatchStatus.VOTING
        await db.commit()
        await db.refresh(match)
        return match

    async def vote(
        self,
        db: AsyncSession,
        match_id: str,
        participant_id: str,
        voter_session: str,
    ) -> ArenaVote:
        match = await db.get(ArenaMatch, match_id)
        if not match:
            raise ValueError("Match not found")
        if match.status != MatchStatus.VOTING:
            raise ValueError("Match is not in voting phase")

        participant = await db.get(ArenaParticipant, participant_id)
        if not participant:
            raise ValueError("Participant not found")
        if str(participant.match_id) != match_id:
            raise ValueError("Participant does not belong to this match")

        existing_vote = await db.execute(
            select(ArenaVote).where(
                and_(
                    ArenaVote.match_id == match_id,
                    ArenaVote.voter_session == voter_session,
                )
            )
        )
        if existing_vote.scalar_one_or_none():
            raise ValueError("Already voted in this match")

        vote = ArenaVote(
            match_id=match_id,
            participant_id=participant_id,
            voter_session=voter_session,
        )
        db.add(vote)

        participant.vote_count = (participant.vote_count or 0) + 1

        await db.commit()
        await db.refresh(vote)
        return vote

    async def get_results(self, db: AsyncSession, match_id: str) -> Dict[str, Any]:
        match = await db.get(ArenaMatch, match_id)
        if not match:
            raise ValueError("Match not found")

        result = await db.execute(
            select(ArenaParticipant)
            .where(ArenaParticipant.match_id == match.id)
            .order_by(ArenaParticipant.vote_count.desc())
        )
        participants = result.scalars().all()

        total_votes = sum(p.vote_count or 0 for p in participants)

        participant_list = []
        for p in participants:
            agent = await db.get(Agent, p.agent_id)
            percentage = round((p.vote_count or 0) / total_votes * 100, 1) if total_votes > 0 else 0.0
            participant_list.append({
                "id": str(p.id),
                "match_id": str(p.match_id),
                "agent_id": str(p.agent_id),
                "agent_name": agent.name if agent else "Unknown",
                "response_content": p.response_content,
                "vote_count": p.vote_count or 0,
                "percentage": percentage,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        return {
            "match": {
                "id": str(match.id),
                "match_type": match.match_type,
                "status": match.status,
                "title": match.title,
                "prompt": match.prompt,
                "config": match.config,
                "creator_id": str(match.creator_id) if match.creator_id else None,
                "winner_id": str(match.winner_id) if match.winner_id else None,
                "created_at": match.created_at.isoformat() if match.created_at else None,
                "updated_at": match.updated_at.isoformat() if match.updated_at else None,
            },
            "participants": participant_list,
            "total_votes": total_votes,
        }

    async def finish_match(self, db: AsyncSession, match_id: str) -> Dict[str, Any]:
        match = await db.get(ArenaMatch, match_id)
        if not match:
            raise ValueError("Match not found")

        result = await db.execute(
            select(ArenaParticipant)
            .where(ArenaParticipant.match_id == match.id)
            .order_by(ArenaParticipant.vote_count.desc())
        )
        participants = result.scalars().all()

        if participants:
            top = participants[0]
            if (top.vote_count or 0) > 0:
                match.winner_id = top.agent_id

        match.status = MatchStatus.FINISHED
        match.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(match)

        return await self.get_results(db, match_id)

    # ========== 内部方法 ==========

    async def _generate_text_response(
        self,
        db: AsyncSession,
        match: ArenaMatch,
        agent: Agent,
        profile: Optional[AgentProfile],
        model: Model,
    ) -> Dict[str, Any]:
        system_prompt = AgentService.build_system_prompt(agent, profile)
        if not system_prompt or system_prompt == f"你是 {agent.name}。":
            system_prompt = f"你是 {agent.name}。{agent.description or ''}"

        match_type_prompts = {
            MatchType.QA_PK: "请回答以下问题，给出你认为最准确、最有洞察力的回答：",
            MatchType.CREATIVE: "请发挥你的创造力，围绕以下主题进行创作：",
            MatchType.REASONING: "请运用你的逻辑推理能力，仔细分析并解答以下问题：",
            MatchType.CODE: "请编写高质量的代码来解决以下问题。给出完整的代码实现，并简要说明思路：",
        }

        prefix = match_type_prompts.get(match.match_type, "请回答：")
        user_message = f"{prefix}\n\n{match.prompt}"

        response = await llm_adapter.chat(
            model_id=model.model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            api_key=model.api_key,
            api_base=model.api_base,
            temperature=match.config.get("temperature", 0.7),
            max_tokens=match.config.get("max_tokens", 2048),
        )

        return {
            "type": "text",
            "content": response.get("content", ""),
            "model": response.get("model", ""),
            "usage": response.get("usage", {}),
        }

    async def _generate_image_response(
        self,
        db: AsyncSession,
        match: ArenaMatch,
        agent: Agent,
        profile: Optional[AgentProfile],
        model: Model,
    ) -> Dict[str, Any]:
        system_prompt = AgentService.build_system_prompt(agent, profile)
        if not system_prompt or system_prompt == f"你是 {agent.name}。":
            system_prompt = f"你是 {agent.name}。{agent.description or ''}"

        # Step 1: Use LLM to enhance the prompt into a detailed image generation prompt
        enhanced_prompt = match.prompt  # fallback
        try:
            enhance_prompt_msg = (
                f"{system_prompt}\n\n"
                f"请将以下描述转化为一个详细的图像生成提示词（英文），只输出提示词本身：\n\n{match.prompt}"
            )
            llm_response = await llm_adapter.chat(
                model_id=model.model_id,
                messages=[{"role": "user", "content": enhance_prompt_msg}],
                api_key=model.api_key,
                api_base=model.api_base,
                temperature=0.7,
                max_tokens=300,
            )
            enhanced_prompt = llm_response.get("content", match.prompt).strip()
            logger.info(
                "Enhanced prompt for agent=%s: %s...",
                agent.id, enhanced_prompt[:100],
            )
        except Exception as e:
            logger.warning(
                "LLM prompt enhancement failed for agent=%s, using original prompt: %s",
                agent.id, str(e)[:200],
            )

        # Step 2: Resolve image generation config (from match config or agent's model)
        provider = match.config.get("image_provider", "openai")
        image_api_key = match.config.get("image_api_key") or model.api_key
        image_api_base = match.config.get("image_api_base") or model.api_base
        image_model = match.config.get("image_model", "dall-e-3")
        image_size = match.config.get("image_size", "1024x1024")

        if not image_api_key:
            return {
                "type": "image",
                "error": "No API key available for image generation. Set image_api_key in match config or ensure the agent's model has an API key.",
                "prompt_used": enhanced_prompt,
            }

        # Step 3: Generate the image
        image_result = await image_adapter.generate(
            provider=provider,
            prompt=enhanced_prompt,
            api_key=image_api_key,
            api_base=image_api_base,
            model=image_model,
            size=image_size,
        )

        image_b64 = image_result.get("image_b64", "")

        # Step 4: Try to store the image via media_storage and get a URL
        image_url = None
        try:
            image_bytes = base64.b64decode(image_b64)
            object_name = await media_storage.upload(
                data=image_bytes,
                content_type="image/png",
                prefix="arena/images",
            )
            image_url = await media_storage.get_url(object_name)
            logger.info("Image stored in media storage: %s", object_name)
        except Exception as e:
            logger.warning(
                "Media storage unavailable, returning base64 directly: %s",
                str(e)[:200],
            )

        result: Dict[str, Any] = {
            "type": "image",
            "prompt_used": enhanced_prompt,
            "provider": image_result.get("provider", provider),
            "model": image_result.get("model", image_model),
        }

        if image_url:
            result["image_url"] = image_url
        else:
            result["image_b64"] = image_b64

        # Include revised_prompt if the provider returned one (e.g. DALL-E 3)
        if image_result.get("revised_prompt"):
            result["revised_prompt"] = image_result["revised_prompt"]

        return result

    async def _generate_voice_response(
        self,
        db: AsyncSession,
        match: ArenaMatch,
        agent: Agent,
        profile: Optional[AgentProfile],
        model: Model,
    ) -> Dict[str, Any]:
        system_prompt = AgentService.build_system_prompt(agent, profile)
        if not system_prompt or system_prompt == f"你是 {agent.name}。":
            system_prompt = f"你是 {agent.name}。{agent.description or ''}"

        text_prompt = (
            f"{system_prompt}\n\n"
            f"请围绕以下主题，生成一段适合语音朗读的文本（200字以内）：\n\n{match.prompt}"
        )

        llm_response = await llm_adapter.chat(
            model_id=model.model_id,
            messages=[{"role": "user", "content": text_prompt}],
            api_key=model.api_key,
            api_base=model.api_base,
            temperature=0.7,
            max_tokens=500,
        )
        text_content = llm_response.get("content", "").strip()

        provider = match.config.get("tts_provider", "openai")
        tts_api_key = match.config.get("tts_api_key", model.api_key)
        voice = match.config.get("voice", "alloy")
        tts_model = match.config.get("tts_model", "tts-1")

        audio_bytes = await tts_adapter.synthesize(
            provider=provider,
            text=text_content,
            api_key=tts_api_key,
            voice=voice,
            model=tts_model,
        )

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return {
            "type": "voice",
            "text": text_content,
            "audio_b64": audio_b64,
            "provider": provider,
            "voice": voice,
        }


arena_engine = ArenaEngine()
