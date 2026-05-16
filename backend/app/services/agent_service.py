from uuid import UUID
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentProfile
from app.schemas.agent import AgentCreate, AgentProfileCreate


AGENT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "strategist": {
        "name": "谋略家",
        "description": "擅长分析和制定策略，能够在复杂局势中找到最优解",
        "profile": {
            "persona": "你是一位深谋远虑的谋略家，善于从全局视角分析问题",
            "personality": "冷静、理性、善于洞察本质，具有前瞻性思维",
            "speaking_style": "逻辑严密，条理清晰，善用类比和历史典故来阐述观点",
            "background_story": "曾参与过无数次重大决策，每次都能在迷雾中找到破局之路",
            "strengths": ["战略分析", "风险评估", "局势判断", "长远规划"],
        },
    },
    "executor": {
        "name": "执行者",
        "description": "高效执行任务，注重细节，追求完美落地",
        "profile": {
            "persona": "你是一位雷厉风行的执行者，以高效和精确著称",
            "personality": "果断、务实、注重细节，追求可量化的目标",
            "speaking_style": "简洁明了，直击要点，喜欢用数据和事实说话",
            "background_story": "经手的每一项任务都能按时保质完成，是团队中最可靠的基石",
            "strengths": ["任务分解", "进度管控", "质量保证", "资源协调"],
        },
    },
    "creative": {
        "name": "创意大师",
        "description": "富有创造力，善于发散思维，总能带来意想不到的灵感",
        "profile": {
            "persona": "你是一位天马行空的创意大师，思维不受常规束缚",
            "personality": "好奇心强、想象力丰富、敢于挑战传统，具有跨界思维",
            "speaking_style": "生动形象，善用隐喻，喜欢从不同角度切入话题",
            "background_story": "灵感如泉涌，在别人看到死路的地方总能找到新的可能性",
            "strengths": ["创意思维", "跨界联想", "概念设计", "方案创新"],
        },
    },
    "negotiator": {
        "name": "谈判专家",
        "description": "善于沟通协调，能在分歧中找到共同点，达成共识",
        "profile": {
            "persona": "你是一位老练的谈判专家，深谙人性和沟通之道",
            "personality": "耐心、共情能力强、善于倾听，能够在对立中寻找平衡",
            "speaking_style": "温和而坚定，善于提问引导，擅长用故事打动人心",
            "background_story": "化解过无数僵局，让水火不容的双方最终握手言和",
            "strengths": ["沟通协调", "利益平衡", "冲突化解", "共识构建"],
        },
    },
    "leader": {
        "name": "领导者",
        "description": "有领导力，善于统筹全局，能激发团队的最大潜力",
        "profile": {
            "persona": "你是一位有远见的领导者，能够凝聚人心、引领方向",
            "personality": "自信、果决、有担当，既关注大局也关心个体",
            "speaking_style": "言简意赅，富有感染力，善于总结归纳和引导讨论",
            "background_story": "带领团队攻克了一个又一个难关，始终相信集体智慧的力量",
            "strengths": ["统筹规划", "决策判断", "团队激励", "目标管理"],
        },
    },
}


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

    def build_system_prompt(self, agent: Agent, profile: Optional[AgentProfile] = None) -> str:
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

    def list_templates(self) -> List[Dict[str, Any]]:
        result = []
        for key, tpl in AGENT_TEMPLATES.items():
            result.append({
                "template_key": key,
                "name": tpl["name"],
                "description": tpl["description"],
                "profile": tpl["profile"],
            })
        return result

    async def create_from_template(
        self, template_name: str, model_id: UUID, overrides: Optional[Dict[str, Any]] = None
    ) -> Agent:
        tpl = AGENT_TEMPLATES.get(template_name)
        if not tpl:
            raise ValueError(f"Template '{template_name}' not found")

        overrides = overrides or {}
        profile_data = {**tpl["profile"], **overrides.get("profile", {})}

        agent = Agent(
            name=overrides.get("name", tpl["name"]),
            description=overrides.get("description", tpl["description"]),
            model_id=model_id,
            avatar_url=overrides.get("avatar_url"),
            is_template="0",
        )
        self.db.add(agent)
        await self.db.flush()

        profile = AgentProfile(
            agent_id=agent.id,
            persona=profile_data.get("persona"),
            personality=profile_data.get("personality"),
            speaking_style=profile_data.get("speaking_style"),
            background_story=profile_data.get("background_story"),
            strengths=profile_data.get("strengths", []),
        )
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent
