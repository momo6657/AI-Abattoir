"""Battle analysis and evolution integration for Pokemon battles."""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonBattle
from app.services.evolution_service import evolution_service
from app.services.pokemon.elo_rating import elo_rating_service


class PokemonBattleAnalysisService:
    """Summarizes battle logs, records agent experience, and updates ratings."""

    def summarize(self, battle_log: list[dict[str, Any]]) -> dict[str, Any]:
        damage_by_attacker: dict[str, int] = {}
        fainted: list[str] = []
        switches = 0
        for event in battle_log:
            event_type = event.get("event")
            data = event.get("data", {})
            if event_type == "move":
                attacker = data.get("attacker")
                if attacker:
                    damage_by_attacker[attacker] = damage_by_attacker.get(attacker, 0) + int(data.get("damage", 0))
            elif event_type == "faint":
                if data.get("pokemon"):
                    fainted.append(data["pokemon"])
            elif event_type == "switch":
                switches += 1
        mvp = max(damage_by_attacker, key=damage_by_attacker.get) if damage_by_attacker else None
        return {
            "mvp": mvp,
            "damage_by_attacker": damage_by_attacker,
            "fainted": fainted,
            "switches": switches,
            "turn_events": len(battle_log),
        }

    async def finalize_battle(
        self,
        db: AsyncSession,
        battle: PokemonBattle,
        winner_agent_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        summary = self.summarize(battle.battle_log or [])
        battle.summary = {**(battle.summary or {}), **summary}
        await db.commit()

        # Record evolution experience
        for agent_id, label in [
            (battle.player1_agent_id, "win" if battle.player1_agent_id == winner_agent_id else "loss"),
            (battle.player2_agent_id, "win" if battle.player2_agent_id == winner_agent_id else "loss"),
        ]:
            if agent_id:
                await evolution_service.record_experience(
                    db=db,
                    agent_id=agent_id,
                    scene_type="pokemon_battle",
                    context_id=battle.id,
                    decision=f"Completed Pokemon battle {battle.id}",
                    outcome=label,
                    xp_override=120 if label == "win" else 60,
                )

        # Update Elo ratings
        try:
            elo_result = await elo_rating_service.update_ratings_after_battle(
                db=db,
                battle=battle,
                winner_agent_id=winner_agent_id,
            )
            summary["elo"] = {
                "player1": {"old": elo_result.player1_old, "new": elo_result.player1_new, "change": elo_result.player1_change},
                "player2": {"old": elo_result.player2_old, "new": elo_result.player2_new, "change": elo_result.player2_change},
                "expected": {"player1": elo_result.player1_expected, "player2": elo_result.player2_expected},
                "k_factor": elo_result.k_factor,
            }
            await db.commit()
        except Exception:
            pass  # Don't fail battle finalization if Elo update fails

        return summary


pokemon_battle_analysis_service = PokemonBattleAnalysisService()
