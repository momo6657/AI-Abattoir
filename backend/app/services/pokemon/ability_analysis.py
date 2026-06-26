"""Pokemon ability analysis and recommendation service.

Analyzes ability usage and provides strategic recommendations
based on team composition and battle format.
"""

from __future__ import annotations

from typing import Any


# Ability categories and their strategic impact
ABILITY_CATEGORIES = {
    "offensive": {
        "abilities": [
            "huge power", "pure power", "adaptability", "tinted lens",
            "sheer force", "technician", "reckless", "iron fist",
            "strong jaw", "mega launcher", "punk rock", "sharpness",
        ],
        "description": "进攻型特性",
        "impact": "提升伤害输出",
    },
    "defensive": {
        "abilities": [
            "levitate", "flash fire", "water absorb", "volt absorb",
            "sap sipper", "motor drive", "lightning rod", "storm drain",
            "bulletproof", "good as gold", "purifying salt", "earth eater",
        ],
        "description": "防御型特性",
        "impact": "免疫或抵抗特定攻击",
    },
    "speed": {
        "abilities": [
            "chlorophyll", "swift swim", "sand rush", "slush rush",
            "surge surfer", "unburden", "speed boost", "quick feet",
        ],
        "description": "速度型特性",
        "impact": "提升速度或获得先手",
    },
    "utility": {
        "abilities": [
            "intimidate", "inner focus", "own tempo", "oblivious",
            "insomnia", "vital spirit", "water veil", "immunity",
            "limber", "forewarn", "synchronize", "trace",
        ],
        "description": "实用型特性",
        "impact": "提供状态免疫或信息",
    },
    "weather": {
        "abilities": [
            "drought", "drizzle", "sand stream", "snow warning",
            "desolate land", "primordial sea", "delta stream",
        ],
        "description": "天气型特性",
        "impact": "自动设置天气",
    },
    "terrain": {
        "abilities": [
            "psychic surge", "electric surge", "grassy surge", "misty surge",
        ],
        "description": "场地型特性",
        "impact": "自动设置场地",
    },
}


class PokemonAbilityAnalysis:
    """Analyzes Pokemon abilities for strategic value."""

    def analyze_ability(
        self,
        ability: str,
        pokemon_types: list[str] | None = None,
        moves: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze a single ability's strategic value."""
        normalized = ability.lower().strip()

        # Find category
        category = "other"
        impact = "未知"
        for cat_name, cat_def in ABILITY_CATEGORIES.items():
            if normalized in cat_def["abilities"]:
                category = cat_name
                impact = cat_def["impact"]
                break

        # Calculate synergy score
        synergy_score = 0
        synergy_details = []

        # Type synergy
        if pokemon_types:
            if normalized == "flash fire" and "Fire" in pokemon_types:
                synergy_score += 20
                synergy_details.append("火属性 + Flash Fire = 免疫火系攻击并提升威力")
            elif normalized == "water absorb" and "Water" in pokemon_types:
                synergy_score += 20
                synergy_details.append("水属性 + Water Absorb = 免疫水系攻击并恢复HP")
            elif normalized == "levitate" and "Ground" in pokemon_types:
                synergy_score += 15
                synergy_details.append("地面属性 + Levitate = 免疫地面系攻击")
            elif normalized == "sap sipper" and "Grass" in pokemon_types:
                synergy_score += 20
                synergy_details.append("草属性 + Sap Sipper = 免疫草系攻击并提升攻击")

        # Move synergy
        if moves:
            move_list = [m.lower() for m in moves]
            if normalized == "technician":
                weak_moves = [m for m in move_list if m in ["bullet punch", "aqua jet", "ice shard", "shadow sneak"]]
                if weak_moves:
                    synergy_score += 15
                    synergy_details.append(f"Technician 增强先制技能: {', '.join(weak_moves)}")
            elif normalized == "sheer force":
                effect_moves = [m for m in move_list if m in ["flamethrower", "ice beam", "thunderbolt", "earth power"]]
                if effect_moves:
                    synergy_score += 15
                    synergy_details.append(f"Sheer Force 增强有效果的招式: {', '.join(effect_moves)}")
            elif normalized == "reckless":
                recoil_moves = [m for m in move_list if m in ["brave bird", "wild charge", "flare blitz", "head smash"]]
                if recoil_moves:
                    synergy_score += 15
                    synergy_details.append(f"Reckless 增强反冲招式: {', '.join(recoil_moves)}")

        # Rating
        rating = "low"
        if synergy_score >= 20:
            rating = "excellent"
        elif synergy_score >= 15:
            rating = "high"
        elif synergy_score >= 10:
            rating = "medium"

        return {
            "ability": ability,
            "category": category,
            "impact": impact,
            "synergy_score": synergy_score,
            "synergy_details": synergy_details,
            "rating": rating,
        }

    def recommend_ability(
        self,
        species: str,
        pokemon_types: list[str],
        moves: list[str] | None = None,
        battle_format: str = "vgc2024",
    ) -> list[dict[str, Any]]:
        """Recommend abilities for a Pokemon."""
        recommendations = []

        # Type-based recommendations
        for type_name in pokemon_types:
            if type_name == "Fire":
                recommendations.append({
                    "ability": "Flash Fire",
                    "reason": "免疫火系攻击并提升火系招式威力",
                    "priority": "high",
                })
            elif type_name == "Water":
                recommendations.append({
                    "ability": "Water Absorb",
                    "reason": "免疫水系攻击并恢复HP",
                    "priority": "high",
                })
            elif type_name == "Electric":
                recommendations.append({
                    "ability": "Volt Absorb",
                    "reason": "免疫电系攻击并恢复HP",
                    "priority": "high",
                })
            elif type_name == "Grass":
                recommendations.append({
                    "ability": "Sap Sipper",
                    "reason": "免疫草系攻击并提升攻击",
                    "priority": "high",
                })

        # Format-based recommendations
        if battle_format.startswith("vgc"):
            recommendations.append({
                "ability": "Intimidate",
                "reason": "VGC 双打核心特性，降低对手攻击",
                "priority": "high",
            })
            recommendations.append({
                "ability": "Fake Out",
                "reason": "VGC 双打先手控制技能",
                "priority": "medium",
            })

        # Move-based recommendations
        if moves:
            move_list = [m.lower() for m in moves]
            if any(m in move_list for m in ["bullet punch", "aqua jet", "ice shard"]):
                recommendations.append({
                    "ability": "Technician",
                    "reason": "增强低威力先制技能",
                    "priority": "high",
                })

        return recommendations[:5]

    def get_all_abilities(self) -> list[dict[str, Any]]:
        """Get all ability categories."""
        return [
            {
                "category": cat_name,
                "description": cat_def["description"],
                "impact": cat_def["impact"],
                "count": len(cat_def["abilities"]),
                "examples": cat_def["abilities"][:3],
            }
            for cat_name, cat_def in ABILITY_CATEGORIES.items()
        ]


pokemon_ability_analysis = PokemonAbilityAnalysis()
