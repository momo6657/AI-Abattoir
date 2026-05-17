from typing import Dict, List, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.agent import Agent, AgentHierarchy


class HierarchyService:
    """层级指挥系统 - 管理 agent 之间的上下级关系和指令传递"""

    async def create_hierarchy(
        self,
        db: AsyncSession,
        parent_agent_id: UUID,
        child_agent_id: UUID,
        relation_type: str = "command",
        context_id: Optional[UUID] = None,
    ) -> AgentHierarchy:
        if parent_agent_id == child_agent_id:
            raise ValueError("Agent cannot be its own superior")

        # 检查是否会形成循环
        if await self._would_create_cycle(db, parent_agent_id, child_agent_id):
            raise ValueError("This hierarchy relation would create a cycle")

        parent = await db.get(Agent, parent_agent_id)
        child = await db.get(Agent, child_agent_id)
        if not parent or not child:
            raise ValueError("Agent not found")

        # 检查是否已存在关系
        existing = await db.execute(
            select(AgentHierarchy).where(
                AgentHierarchy.parent_agent_id == parent_agent_id,
                AgentHierarchy.child_agent_id == child_agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Hierarchy relation already exists")

        hierarchy = AgentHierarchy(
            parent_agent_id=parent_agent_id,
            child_agent_id=child_agent_id,
            relation_type=relation_type,
            context_id=context_id,
        )
        db.add(hierarchy)
        await db.commit()
        await db.refresh(hierarchy)
        return hierarchy

    async def get_subordinates(
        self, db: AsyncSession, agent_id: UUID
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(AgentHierarchy, Agent)
            .join(Agent, AgentHierarchy.child_agent_id == Agent.id)
            .where(AgentHierarchy.parent_agent_id == agent_id)
        )
        rows = result.all()

        subordinates = []
        for rel, agent in rows:
            subordinates.append({
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "relation_type": rel.relation_type,
                "context_id": str(rel.context_id) if rel.context_id else None,
            })
        return subordinates

    async def get_superior(
        self, db: AsyncSession, agent_id: UUID
    ) -> Optional[Dict[str, Any]]:
        result = await db.execute(
            select(AgentHierarchy, Agent)
            .join(Agent, AgentHierarchy.parent_agent_id == Agent.id)
            .where(AgentHierarchy.child_agent_id == agent_id)
        )
        row = result.one_or_none()
        if not row:
            return None

        relation, agent = row
        return {
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "relation_type": relation.relation_type,
            "context_id": str(relation.context_id) if relation.context_id else None,
        }

    async def get_hierarchy_tree(
        self, db: AsyncSession, root_agent_id: UUID
    ) -> Dict[str, Any]:
        agent = await db.get(Agent, root_agent_id)
        if not agent:
            raise ValueError("Agent not found")

        return await self._build_tree(db, root_agent_id, set())

    async def _build_tree(
        self, db: AsyncSession, agent_id: UUID, visited: set
    ) -> Dict[str, Any]:
        if agent_id in visited:
            return {"agent_id": str(agent_id), "circular": True}

        visited.add(agent_id)
        agent = await db.get(Agent, agent_id)
        subordinates = await self.get_subordinates(db, agent_id)

        children = []
        for sub in subordinates:
            child_tree = await self._build_tree(
                db, UUID(sub["agent_id"]), visited.copy()
            )
            children.append(child_tree)

        return {
            "agent_id": str(agent.id) if agent else str(agent_id),
            "agent_name": agent.name if agent else "Unknown",
            "subordinates": children,
        }

    async def check_authority(
        self, db: AsyncSession, agent_id: UUID, target_agent_id: UUID
    ) -> bool:
        # 直接下级
        result = await db.execute(
            select(AgentHierarchy).where(
                AgentHierarchy.parent_agent_id == agent_id,
                AgentHierarchy.child_agent_id == target_agent_id,
            )
        )
        if result.scalar_one_or_none():
            return True

        # 检查传递性（间接下级，最多5层）
        return await self._check_transitive(db, agent_id, target_agent_id, max_depth=5)

    async def _check_transitive(
        self,
        db: AsyncSession,
        agent_id: UUID,
        target_id: UUID,
        max_depth: int,
        current_depth: int = 0,
    ) -> bool:
        if current_depth >= max_depth:
            return False

        result = await db.execute(
            select(AgentHierarchy).where(AgentHierarchy.parent_agent_id == agent_id)
        )
        relations = result.scalars().all()

        for rel in relations:
            if rel.child_agent_id == target_id:
                return True
            if await self._check_transitive(
                db, rel.child_agent_id, target_id, max_depth, current_depth + 1
            ):
                return True

        return False

    async def _would_create_cycle(
        self, db: AsyncSession, parent_id: UUID, child_id: UUID
    ) -> bool:
        """检查 parent 是否已经是 child 的下级（避免循环）"""
        return await self._check_transitive(db, child_id, parent_id, max_depth=10)


hierarchy_service = HierarchyService()
