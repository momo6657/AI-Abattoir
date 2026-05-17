from uuid import UUID
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentProfile
from app.schemas.agent import AgentCreate, AgentProfileCreate


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_agent(
        self, agent_data: AgentCreate, profile_data: Optional[AgentProfileCreate] = None
    ) -> Agent:
        agent = Agent(
            name=agent_data.name,
            description=agent_data.description,
            model_id=agent_data.model_id,
            avatar_url=agent_data.avatar_url,
            voice_model_id=agent_data.voice_model_id,
        )
        self.db.add(agent)
        await self.db.flush()

        profile_src = profile_data or agent_data.profile
        if profile_src:
            profile = AgentProfile(
                agent_id=agent.id,
                persona=profile_src.persona,
                personality=profile_src.personality,
                speaking_style=profile_src.speaking_style,
                background_story=profile_src.background_story,
                strengths=profile_src.strengths,
                system_prompt=profile_src.system_prompt,
                custom_config=profile_src.custom_config,
            )
            self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_agent_with_profile(self, agent_id: UUID) -> Tuple[Optional[Agent], Optional[AgentProfile]]:
        agent = await self.db.get(Agent, agent_id)
        if not agent:
            return None, None
        result = await self.db.execute(
            select(AgentProfile).where(AgentProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        return agent, profile

    @staticmethod
    def build_system_prompt(agent: Agent, profile: Optional[AgentProfile] = None) -> str:
        if profile is None:
            return f"你是 {agent.name}。{agent.description or ''}"

        parts = [f"你是 {agent.name}。"]
        if profile.system_prompt:
            return profile.system_prompt
        if profile.persona:
            parts.append(profile.persona)
        if profile.personality:
            parts.append(f"性格特点：{profile.personality}")
        if profile.speaking_style:
            parts.append(f"说话风格：{profile.speaking_style}")
        if profile.background_story:
            parts.append(f"背景：{profile.background_story}")
        if profile.strengths:
            parts.append(f"擅长领域：{', '.join(profile.strengths)}")
        return "\n".join(parts)
