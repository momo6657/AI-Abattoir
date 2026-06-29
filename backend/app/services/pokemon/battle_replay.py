"""Battle replay service for Pokemon battles.

Converts battle logs into structured replay data that can be
stepped through turn-by-turn on the frontend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonBattle, PokemonTeam
from app.services.pokemon.battle_outcome import winner_agent_id, winner_side


@dataclass
class ReplayFrame:
    """A single frame in a battle replay."""
    turn: int
    event_index: int
    event_type: str
    event_data: dict[str, Any]
    description: str
    side_effects: list[str] = field(default_factory=list)


@dataclass
class ReplayTurn:
    """All events in a single turn."""
    turn: int
    frames: list[ReplayFrame] = field(default_factory=list)
    summary: str = ""


@dataclass
class BattleReplay:
    """Complete structured replay of a battle."""
    battle_id: str
    format: str
    turns: list[ReplayTurn] = field(default_factory=list)
    total_turns: int = 0
    winner: str | None = None
    winner_side: int | None = None
    team1: dict[str, Any] = field(default_factory=dict)
    team2: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_id": self.battle_id,
            "format": self.format,
            "total_turns": self.total_turns,
            "winner": self.winner,
            "winner_side": self.winner_side,
            "team1": self.team1,
            "team2": self.team2,
            "summary": self.summary,
            "turns": [
                {
                    "turn": t.turn,
                    "summary": t.summary,
                    "frames": [
                        {
                            "event_index": f.event_index,
                            "event_type": f.event_type,
                            "event_data": f.event_data,
                            "description": f.description,
                            "side_effects": f.side_effects,
                        }
                        for f in t.frames
                    ],
                }
                for t in self.turns
            ],
        }


class PokemonBattleReplayService:
    """Builds and retrieves battle replays."""

    def _describe_event(self, event: dict[str, Any]) -> str:
        """Generate a human-readable description of a battle event."""
        event_type = event.get("event", "unknown")
        data = event.get("data", {})
        turn = event.get("turn", "?")

        if event_type == "move":
            attacker = data.get("attacker", data.get("pokemon", "?"))
            move = data.get("move", "?")
            target = data.get("target", "")
            if target:
                return f"T{turn}: {attacker} 对 {target} 使用了 {move}"
            return f"T{turn}: {attacker} 使用了 {move}"

        if event_type == "damage":
            target = data.get("target", "?")
            damage = data.get("damage", 0)
            return f"T{turn}: {target} 受到了 {damage} 点伤害"

        if event_type == "faint":
            pokemon = data.get("pokemon", "?")
            return f"T{turn}: {pokemon} 倒下了"

        if event_type == "switch":
            player = data.get("player", "?")
            frm = data.get("from", "?")
            to = data.get("to", "?")
            return f"T{turn}: 玩家{player} 将 {frm} 换成了 {to}"

        if event_type == "heal":
            target = data.get("target", "?")
            amount = data.get("amount", 0)
            return f"T{turn}: {target} 恢复了 {amount} HP"

        if event_type == "status":
            target = data.get("target", "?")
            status = data.get("status", "?")
            return f"T{turn}: {target} 陷入了 {status} 状态"

        if event_type == "weather":
            weather = data.get("weather", "?")
            return f"T{turn}: 天气变为 {weather}"

        if event_type == "terastallize":
            pokemon = data.get("pokemon", "?")
            tera_type = data.get("tera_type", "?")
            return f"T{turn}: {pokemon} 太晶化为 {tera_type}"

        if event_type == "turn_start":
            return f"T{turn}: === 回合 {turn} 开始 ==="

        if event_type == "turn_end":
            return f"T{turn}: === 回合 {turn} 结束 ==="

        return f"T{turn}: {event_type}"

    def build_replay(
        self,
        battle: PokemonBattle,
        team1_data: dict[str, Any] | None = None,
        team2_data: dict[str, Any] | None = None,
    ) -> BattleReplay:
        """Build a structured replay from a battle record."""
        resolved_winner_agent = winner_agent_id(battle)
        resolved_winner_side = winner_side(battle)
        replay = BattleReplay(
            battle_id=str(battle.id),
            format=battle.battle_format or "unknown",
            winner=str(resolved_winner_agent or battle.winner) if battle.winner else None,
            winner_side=resolved_winner_side,
            team1=team1_data or {},
            team2=team2_data or {},
            summary=battle.summary or {},
        )

        battle_log = battle.battle_log or []
        current_turn = 0
        current_replay_turn: ReplayTurn | None = None
        event_index = 0

        for event in battle_log:
            turn = event.get("turn", current_turn)
            if turn != current_turn:
                if current_replay_turn:
                    replay.turns.append(current_replay_turn)
                current_turn = turn
                current_replay_turn = ReplayTurn(turn=turn)
                event_index = 0

            if current_replay_turn is None:
                current_replay_turn = ReplayTurn(turn=turn)

            frame = ReplayFrame(
                turn=turn,
                event_index=event_index,
                event_type=event.get("event", "unknown"),
                event_data=event.get("data", {}),
                description=self._describe_event(event),
            )
            current_replay_turn.frames.append(frame)
            event_index += 1

        if current_replay_turn:
            replay.turns.append(current_replay_turn)

        replay.total_turns = battle.turns or current_turn
        return replay

    async def get_battle_replay(
        self,
        db: AsyncSession,
        battle_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Retrieve and build a replay for a battle."""
        battle = await db.get(PokemonBattle, battle_id)
        if not battle:
            return None

        # Load team data if available
        team1_data = {}
        team2_data = {}
        if battle.player1_team_id:
            team1 = await db.get(PokemonTeam, battle.player1_team_id)
            if team1:
                team1_data = {
                    "name": team1.name,
                    "format": team1.format,
                    "pokemon": team1.pokemon_list or [],
                }
        if battle.player2_team_id:
            team2 = await db.get(PokemonTeam, battle.player2_team_id)
            if team2:
                team2_data = {
                    "name": team2.name,
                    "format": team2.format,
                    "pokemon": team2.pokemon_list or [],
                }

        replay = self.build_replay(battle, team1_data, team2_data)
        return replay.to_dict()

    async def get_recent_replays(
        self,
        db: AsyncSession,
        agent_id: uuid.UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent battle replays, optionally filtered by agent."""
        query = (
            select(PokemonBattle)
            .where(PokemonBattle.battle_log.isnot(None))
            .order_by(PokemonBattle.created_at.desc())
            .limit(limit)
        )
        if agent_id:
            query = query.where(
                (PokemonBattle.player1_agent_id == agent_id)
                | (PokemonBattle.player2_agent_id == agent_id)
            )

        result = await db.execute(query)
        battles = result.scalars().all()

        replays = []
        for battle in battles:
            replay = self.build_replay(battle)
            replays.append({
                "battle_id": str(battle.id),
                "format": battle.battle_format,
                "total_turns": replay.total_turns,
                "winner": replay.winner,
                "created_at": battle.created_at.isoformat() if battle.created_at else None,
                "turn_count": len(replay.turns),
                "event_count": sum(len(t.frames) for t in replay.turns),
            })
        return replays


pokemon_battle_replay_service = PokemonBattleReplayService()
