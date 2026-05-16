from typing import Dict, List, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.agent import Agent, AgentLevel, AgentExperience
from app.models.model import Model
from app.services.llm_adapter import llm_adapter


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

    async def extract_lesson(
        self, db: AsyncSession, experience_id: UUID
    ) -> str:
        exp = await db.get(AgentExperience, experience_id)
        if not exp:
            raise ValueError("Experience not found")

        agent = await db.get(Agent, exp.agent_id)
        model = await db.get(Model, agent.model_id) if agent else None

        if not model:
            lesson = f"场景：{exp.scene_type}，决策：{exp.decision}，结果：{exp.outcome}"
            exp.lesson = lesson
            await db.commit()
            return lesson

        prompt = f"""分析以下经验，提取一条简洁的教训（50字以内）：

场景类型：{exp.scene_type}
决策：{exp.decision}
结果：{exp.outcome}

请用一句话总结从这次经历中可以学到什么。"""

        try:
            response = await llm_adapter.chat(
                model_id=model.model_id,
                messages=[{"role": "user", "content": prompt}],
                api_key=model.api_key,
                api_base=model.api_base,
                temperature=0.5,
                max_tokens=200,
            )
            lesson = response.get("content", "").strip()
        except Exception:
            lesson = f"从{exp.scene_type}中学到：{exp.decision} -> {exp.outcome}"

        exp.lesson = lesson
        await db.commit()
        return lesson

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

    async def get_evolution_prompt(
        self, db: AsyncSession, agent_id: UUID
    ) -> str:
        agent = await db.get(Agent, agent_id)
        if not agent:
            return ""

        # 获取最近的经验教训
        result = await db.execute(
            select(AgentExperience)
            .where(AgentExperience.agent_id == agent_id)
            .where(AgentExperience.lesson.isnot(None))
            .order_by(AgentExperience.created_at.desc())
            .limit(5)
        )
        experiences = result.scalars().all()

        if not experiences:
            return ""

        lessons = [exp.lesson for exp in experiences if exp.lesson]
        if not lessons:
            return ""

        level_info = f"等级：{agent.level.value}（{agent.experience_points} XP）"
        lessons_text = "\n".join(f"- {l}" for l in lessons)

        return f"""{level_info}
过往经验教训：
{lessons_text}

请基于以上经验做出更好的决策。"""

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

    async def transfer_experience(
        self,
        db: AsyncSession,
        agent_id: UUID,
        from_scene: str,
        to_scene: str,
    ) -> Dict[str, Any]:
        result = await db.execute(
            select(AgentExperience)
            .where(AgentExperience.agent_id == agent_id)
            .where(AgentExperience.scene_type == from_scene)
            .where(AgentExperience.lesson.isnot(None))
            .order_by(AgentExperience.created_at.desc())
            .limit(3)
        )
        experiences = result.scalars().all()

        if not experiences:
            return {"transferred": 0, "message": "No experiences to transfer"}

        agent = await db.get(Agent, agent_id)
        model = await db.get(Model, agent.model_id) if agent else None

        lessons = [exp.lesson for exp in experiences if exp.lesson]
        transferred_count = 0

        if model and lessons:
            prompt = f"""将以下从 {from_scene} 场景中获得的经验教训，转化为适用于 {to_scene} 场景的建议：

原始教训：
{chr(10).join('- ' + l for l in lessons)}

请输出 {to_scene} 场景下可以复用的经验，50字以内。"""

            try:
                response = await llm_adapter.chat(
                    model_id=model.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=model.api_key,
                    api_base=model.api_base,
                    temperature=0.5,
                    max_tokens=200,
                )
                adapted_lesson = response.get("content", "").strip()

                new_exp = AgentExperience(
                    agent_id=agent_id,
                    scene_type=to_scene,
                    context_id=None,
                    decision=f"经验迁移自 {from_scene}",
                    outcome="迁移经验",
                    lesson=adapted_lesson,
                    xp_gained=5,
                )
                db.add(new_exp)
                agent.experience_points = (agent.experience_points or 0) + 5
                agent.level = self._level_from_xp(agent.experience_points)
                transferred_count = 1
            except Exception:
                pass

        await db.commit()
        return {
            "transferred": transferred_count,
            "source_lessons": lessons,
            "target_scene": to_scene,
        }

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
