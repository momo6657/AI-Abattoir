from typing import Dict, List, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.agent import Agent, AgentLevel, AgentExperience


# 等级阈值
LEVEL_THRESHOLDS = [
    (AgentLevel.NOVICE, 0),
    (AgentLevel.PROFICIENT, 100),
    (AgentLevel.EXPERT, 500),
    (AgentLevel.MASTER, 1500),
]


class EvolutionService:
    """经验学习与进化系统"""

    async def record_experience(
        self,
        db: AsyncSession,
        agent_id: UUID,
        scene_type: str,
        context_id: Optional[UUID],
        decision: str,
        outcome: str,
        xp_override: Optional[int] = None,
    ) -> AgentExperience:
        agent = await db.get(Agent, agent_id)
        if not agent:
            raise ValueError("Agent not found")

        xp = xp_override or self._calculate_xp(scene_type, outcome)

        experience = AgentExperience(
            agent_id=agent_id,
            scene_type=scene_type,
            context_id=context_id,
            decision=decision,
            outcome=outcome,
            xp_gained=xp,
        )
        db.add(experience)

        # 更新 agent 经验值
        agent.experience_points = (agent.experience_points or 0) + xp
        new_level = self._level_from_xp(agent.experience_points)
        agent.level = new_level

        await db.commit()
        await db.refresh(experience)
        return experience

    async def calculate_level(self, db: AsyncSession, agent_id: UUID) -> Dict[str, Any]:
        agent = await db.get(Agent, agent_id)
        if not agent:
            raise ValueError("Agent not found")

        xp = agent.experience_points or 0
        level = self._level_from_xp(xp)
        next_level_xp = self._next_level_xp(xp)

        return {
            "agent_id": str(agent_id),
            "level": level.value,
            "xp": xp,
            "next_level_xp": next_level_xp,
            "progress": self._calc_progress(xp),
        }

    async def get_growth_log(
        self, db: AsyncSession, agent_id: UUID
    ) -> List[Dict[str, Any]]:
        agent = await db.get(Agent, agent_id)
        if not agent:
            raise ValueError("Agent not found")

        result = await db.execute(
            select(AgentExperience)
            .where(AgentExperience.agent_id == agent_id)
            .order_by(AgentExperience.created_at.asc())
        )
        experiences = result.scalars().all()

        log = []
        cumulative_xp = 0
        for exp in experiences:
            cumulative_xp += exp.xp_gained or 0
            log.append({
                "id": str(exp.id),
                "scene_type": exp.scene_type,
                "decision": exp.decision,
                "outcome": exp.outcome,
                "lesson": exp.lesson,
                "xp_gained": exp.xp_gained,
                "cumulative_xp": cumulative_xp,
                "level_at_time": self._level_from_xp(cumulative_xp).value,
                "created_at": exp.created_at.isoformat() if exp.created_at else None,
            })

        return log

    # ========== 辅助方法 ==========

    def _calculate_xp(self, scene_type: str, outcome: str) -> int:
        import random
        base = {
            "conversation": (5, 20),
            "arena_pk": (10, 50),
            "game": (20, 100),
        }
        xp_range = base.get(scene_type, (5, 20))
        xp = random.randint(*xp_range)

        # 胜利加成
        if outcome and "win" in outcome.lower():
            xp = int(xp * 1.5)
        return xp

    def _level_from_xp(self, xp: int) -> AgentLevel:
        level = AgentLevel.NOVICE
        for lvl, threshold in LEVEL_THRESHOLDS:
            if xp >= threshold:
                level = lvl
        return level

    def _next_level_xp(self, xp: int) -> Optional[int]:
        for lvl, threshold in LEVEL_THRESHOLDS:
            if xp < threshold:
                return threshold
        return None

    def _calc_progress(self, xp: int) -> float:
        current_threshold = 0
        next_threshold = None
        for lvl, threshold in LEVEL_THRESHOLDS:
            if xp >= threshold:
                current_threshold = threshold
            elif next_threshold is None:
                next_threshold = threshold

        if next_threshold is None:
            return 1.0
        range_size = next_threshold - current_threshold
        if range_size <= 0:
            return 1.0
        return min(1.0, (xp - current_threshold) / range_size)


evolution_service = EvolutionService()
