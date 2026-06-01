"""Lightweight reinforcement-learning helpers for Pokemon battle decisions."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonDecision


class PokemonRLService:
    """Records state-action-reward rows and retrieves similar decisions."""

    def state_hash(self, state: dict[str, Any]) -> str:
        normalized = json.dumps(state, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def record_decision(
        self,
        db: AsyncSession,
        battle_id: uuid.UUID,
        agent_id: uuid.UUID,
        turn: int,
        state: dict[str, Any],
        action: dict[str, Any],
        alternatives: list[dict[str, Any]] | None = None,
        confidence: float | None = None,
        immediate_reward: float = 0.0,
        llm_reasoning: str | None = None,
    ) -> PokemonDecision:
        decision = PokemonDecision(
            id=uuid.uuid4(),
            battle_id=battle_id,
            agent_id=agent_id,
            turn=turn,
            state_hash=self.state_hash(state),
            state=state,
            action=action,
            alternatives=alternatives or [],
            confidence=confidence,
            llm_reasoning=llm_reasoning,
            immediate_reward=immediate_reward,
            q_value=immediate_reward,
        )
        db.add(decision)
        await db.commit()
        await db.refresh(decision)
        return decision

    async def similar_decisions(
        self,
        db: AsyncSession,
        agent_id: uuid.UUID,
        state: dict[str, Any],
        limit: int = 5,
    ) -> list[PokemonDecision]:
        result = await db.execute(
            select(PokemonDecision)
            .where(PokemonDecision.agent_id == agent_id)
            .where(PokemonDecision.state_hash == self.state_hash(state))
            .order_by(PokemonDecision.q_value.desc().nullslast())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_final_rewards(
        self,
        db: AsyncSession,
        battle_id: uuid.UUID,
        winning_agent_id: uuid.UUID | None,
    ) -> int:
        result = await db.execute(
            select(PokemonDecision).where(PokemonDecision.battle_id == battle_id)
        )
        decisions = list(result.scalars().all())
        for decision in decisions:
            final_reward = 0.0
            if winning_agent_id:
                final_reward = 100.0 if decision.agent_id == winning_agent_id else -100.0
            decision.final_reward = final_reward
            decision.q_value = (decision.immediate_reward or 0.0) + final_reward
        await db.commit()
        return len(decisions)

    def reward_from_turn_events(self, events: list[dict[str, Any]], agent_side: int) -> float:
        reward = 0.0
        for event in events:
            if event.get("event") == "move":
                data = event.get("data", {})
                reward += min(float(data.get("damage", 0)), 100.0) / 10.0
            elif event.get("event") == "faint":
                reward += 50.0
        return reward if agent_side == 1 else reward


pokemon_rl_service = PokemonRLService()
