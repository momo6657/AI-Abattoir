"""Pokemon item analysis and recommendation service.

Analyzes item usage patterns and provides recommendations
based on team composition and battle format.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonTeam


# Item categories and their strategic purposes
ITEM_CATEGORIES = {
    "offensive": {
        "items": ["choice band", "choice specs", "life orb", "scope lens", "razor claw"],
        "description": "进攻型道具",
        "purpose": "提升伤害输出",
    },
    "defensive": {
        "items": ["leftovers", "rocky helmet", "assault vest", "focus sash", "safety goggles"],
        "description": "防御型道具",
        "purpose": "提升生存能力",
    },
    "speed": {
        "items": ["choice scarf", "iron ball", "macho brace"],
        "description": "速度型道具",
        "purpose": "调整速度线",
    },
    "utility": {
        "items": ["sitrus berry", "lum berry", "berry juice", "weakness policy", "throat spray"],
        "description": "实用型道具",
        "purpose": "提供特殊效果",
    },
    "type_boost": {
        "items": [
            "charcoal", "mystic water", "miracle seed", "magnet", "never-melt ice",
            "black belt", "poison barb", "soft sand", "sharp beak", "twisted spoon",
            "silver powder", "hard stone", "spell tag", "dragon fang", "black glasses",
            "metal coat", "silk scarf",
        ],
        "description": "属性增强道具",
        "purpose": "提升特定属性招式威力",
    },
}


class PokemonItemAnalysis:
    """Analyzes Pokemon item usage and provides recommendations."""

    def analyze_item_distribution(
        self,
        team: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze item distribution in a team."""
        items = []
        for pokemon in team:
            item = pokemon.get("item")
            if item:
                items.append(item.lower())

        # Count items
        item_counts = Counter(items)

        # Categorize items
        categories: dict[str, int] = Counter()
        for item in items:
            for cat_name, cat_def in ITEM_CATEGORIES.items():
                if item in cat_def["items"]:
                    categories[cat_name] += 1
                    break
            else:
                categories["other"] += 1

        # Check for issues
        issues = []
        if not items:
            issues.append("队伍中没有道具配置")
        elif len(set(items)) < len(items):
            issues.append("存在重复道具，可能违反规则")

        # Check for focus sash (important for singles)
        has_focus_sash = "focus sash" in items
        has_leftovers = "leftovers" in items

        return {
            "items": items,
            "item_counts": dict(item_counts),
            "categories": dict(categories),
            "unique_items": len(set(items)),
            "has_focus_sash": has_focus_sash,
            "has_leftovers": has_leftovers,
            "issues": issues,
        }

    def recommend_items(
        self,
        pokemon: dict[str, Any],
        battle_format: str = "vgc2024",
        team_items: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Recommend items for a Pokemon based on its role and format."""
        recommendations = []
        species = pokemon.get("species") or pokemon.get("name", "")
        types = pokemon.get("types", [])
        moves = pokemon.get("moves", [])
        ability = pokemon.get("ability", "")

        # Analyze role from moves
        has_setup = any(
            m.lower() in ["swords dance", "nasty plot", "dragon dance", "quiver dance"]
            for m in moves
        )
        has_priority = any(
            m.lower() in ["extreme speed", "bullet punch", "aqua jet", "ice shard", "shadow sneak", "sucker punch"]
            for m in moves
        )
        has_protect = "protect" in [m.lower() for m in moves]

        # VGC recommendations
        if battle_format.startswith("vgc"):
            if has_protect:
                recommendations.append({
                    "item": "Sitrus Berry",
                    "reason": "VGC 双打常用回复道具，配合 Protect 使用",
                    "priority": "high",
                })
            if has_setup:
                recommendations.append({
                    "item": "Life Orb",
                    "reason": "强化型宝可梦适合使用生命宝珠提升伤害",
                    "priority": "high",
                })
            if has_priority:
                recommendations.append({
                    "item": "Choice Band",
                    "reason": "先制技能手适合使用力量头带提升伤害",
                    "priority": "medium",
                })

        # Singles recommendations
        elif battle_format in ["gen9ou", "gen9uu", "gen9ru"]:
            recommendations.append({
                "item": "Leftovers",
                "reason": "单打中最通用的回复道具",
                "priority": "high",
            })
            if has_setup:
                recommendations.append({
                    "item": "Life Orb",
                    "reason": "强化型宝可梦适合使用生命宝珠",
                    "priority": "high",
                })

        # Type-boost recommendations
        for type_name in types:
            type_items = {
                "Fire": "Charcoal",
                "Water": "Mystic Water",
                "Grass": "Miracle Seed",
                "Electric": "Magnet",
                "Ice": "Never-Melt Ice",
                "Fighting": "Black Belt",
                "Poison": "Poison Barb",
                "Ground": "Soft Sand",
                "Flying": "Sharp Beak",
                "Psychic": "Twisted Spoon",
                "Bug": "Silver Powder",
                "Rock": "Hard Stone",
                "Ghost": "Spell Tag",
                "Dragon": "Dragon Fang",
                "Dark": "Black Glasses",
                "Steel": "Metal Coat",
                "Fairy": "Silk Scarf",
                "Normal": "Silk Scarf",
            }
            if type_name in type_items:
                recommendations.append({
                    "item": type_items[type_name],
                    "reason": f"增强 {type_name} 属性招式威力 20%",
                    "priority": "low",
                })

        # Remove duplicates and already used items
        seen = set()
        filtered = []
        for rec in recommendations:
            if rec["item"].lower() not in seen:
                if not team_items or rec["item"].lower() not in [t.lower() for t in team_items]:
                    seen.add(rec["item"].lower())
                    filtered.append(rec)

        return filtered[:5]

    async def get_popular_items(
        self,
        db: AsyncSession,
        battle_format: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get most popular items across all teams."""
        query = select(PokemonTeam)
        if battle_format:
            query = query.where(PokemonTeam.format == battle_format)
        result = await db.execute(query)
        teams = result.scalars().all()

        item_counts: Counter = Counter()
        for team in teams:
            for pokemon in (team.pokemon_list or []):
                item = pokemon.get("item")
                if item:
                    item_counts[item] += 1

        return [
            {"item": item, "usage_count": count}
            for item, count in item_counts.most_common(limit)
        ]


pokemon_item_analysis = PokemonItemAnalysis()
