"""Agent-aware Pokemon team building."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentLevel
from app.models.pokemon import PokemonTeam


DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "pokemon"


class PokemonTeamBuilder:
    """Builds teams from templates now, with hooks for later innovation."""

    def load_templates(self, battle_format: str = "vgc2024") -> list[dict[str, Any]]:
        path = DATA_DIR / "team_templates.json"
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return [
            template for template in data.get("team_templates", [])
            if template.get("format", "vgc2024") == battle_format
        ]

    async def build_for_agent(
        self,
        db: AsyncSession,
        agent: Agent,
        battle_format: str = "vgc2024",
    ) -> PokemonTeam:
        template = self.select_template(agent, battle_format)
        pokemon = template["pokemon"]
        source = "template"
        if agent.level in {AgentLevel.EXPERT, AgentLevel.MASTER}:
            pokemon = self._light_innovation(pokemon, agent)
            source = "evolved"

        team = PokemonTeam(
            id=uuid.uuid4(),
            agent_id=agent.id,
            name=f"{agent.name} - {template['name']}",
            format=battle_format,
            pokemon_list=pokemon,
            source=source,
            source_url=template.get("source_url"),
        )
        db.add(team)
        await db.commit()
        await db.refresh(team)
        return team

    def select_template(self, agent: Agent, battle_format: str = "vgc2024") -> dict[str, Any]:
        templates = self.load_templates(battle_format)
        if not templates:
            raise ValueError(f"No Pokemon team templates for format: {battle_format}")

        playstyle = (agent.pokemon_playstyle or "").lower()
        if "rain" in playstyle:
            return self._find_template(templates, "rain") or templates[0]
        if "trick" in playstyle or "slow" in playstyle:
            return self._find_template(templates, "trick") or templates[0]
        if "offense" in playstyle or "sun" in playstyle:
            return self._find_template(templates, "sun") or templates[0]
        if agent.level == AgentLevel.NOVICE:
            return templates[0]
        if agent.level == AgentLevel.PROFICIENT:
            return templates[min(1, len(templates) - 1)]
        return max(templates, key=lambda item: len(item.get("pokemon", [])))

    def _find_template(self, templates: list[dict[str, Any]], keyword: str) -> dict[str, Any] | None:
        for template in templates:
            haystack = f"{template.get('id', '')} {template.get('name', '')} {template.get('description', '')}".lower()
            if keyword in haystack:
                return template
        return None

    def _light_innovation(self, pokemon: list[dict[str, Any]], agent: Agent) -> list[dict[str, Any]]:
        evolved = [dict(member) for member in pokemon]
        if not evolved:
            return evolved
        stats = agent.pokemon_stats or {}
        favorite_items = stats.get("successful_items") or []
        if favorite_items:
            evolved[0]["item"] = favorite_items[0]
        for member in evolved:
            member.setdefault("tera_type", self._default_tera_type(member))
        return evolved

    def _default_tera_type(self, pokemon: dict[str, Any]) -> str:
        moves = pokemon.get("moves", [])
        if any("Protect" == move for move in moves):
            return "Water"
        return "Normal"


pokemon_team_builder = PokemonTeamBuilder()
