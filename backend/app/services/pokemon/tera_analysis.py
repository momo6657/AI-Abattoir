"""Pokemon Terastallize analysis and recommendation service.

Analyzes Tera type choices and provides strategic recommendations
based on team composition and battle format.
"""

from __future__ import annotations

from typing import Any

from app.services.pokemon.type_chart import TypeChart


# Tera type strategic categories
TERA_CATEGORIES = {
    "offensive": {
        "types": ["Fire", "Water", "Grass", "Electric", "Ice", "Fighting", "Ground", "Rock", "Dragon", "Dark", "Steel", "Fairy"],
        "description": "进攻型太晶",
        "purpose": "提升特定属性招式威力或获得 STAB",
    },
    "defensive": {
        "types": ["Steel", "Fairy", "Water", "Ghost", "Flying", "Dragon"],
        "description": "防御型太晶",
        "purpose": "改变弱点属性或获得抗性",
    },
    "surprise": {
        "types": ["Normal", "Ghost", "Ground", "Electric"],
        "description": "出其不意型太晶",
        "purpose": "出其不意改变属性获得优势",
    },
}


class PokemonTeraAnalysis:
    """Analyzes Terastallize type choices for strategic value."""

    def __init__(self):
        self.type_chart = TypeChart()

    def analyze_tera_type(
        self,
        tera_type: str,
        pokemon_types: list[str],
        moves: list[dict[str, Any] | str] | None = None,
        ability: str | None = None,
    ) -> dict[str, Any]:
        """Analyze a Tera type choice for a Pokemon."""
        # Check if Tera type matches existing types
        is_same_type = tera_type in pokemon_types

        # Calculate offensive benefits
        offensive_benefits = []
        if moves:
            for move in moves:
                move_type = None
                if isinstance(move, dict):
                    move_type = move.get("type")
                elif isinstance(move, str):
                    from app.services.pokemon.move_analysis import pokemon_move_analysis
                    move_type = pokemon_move_analysis._infer_move_type(move)

                if move_type == tera_type and not is_same_type:
                    offensive_benefits.append({
                        "move": move if isinstance(move, str) else move.get("name", "Unknown"),
                        "benefit": "获得 STAB 加成 (1.5x)",
                    })
                elif move_type == tera_type and is_same_type:
                    offensive_benefits.append({
                        "move": move if isinstance(move, str) else move.get("name", "Unknown"),
                        "benefit": "STAB 提升至 2x (Adaptability 效果)",
                    })

        # Calculate defensive benefits
        defensive_benefits = []
        weaknesses_before = []
        weaknesses_after = []
        resistances_before = []
        resistances_after = []

        for attacking_type in self.type_chart.types:
            eff_before = self.type_chart.get_dual_type_effectiveness(attacking_type, pokemon_types)
            eff_after = self.type_chart.get_effectiveness(attacking_type, tera_type)

            if eff_before > 1:
                weaknesses_before.append(attacking_type)
            if eff_after > 1:
                weaknesses_after.append(attacking_type)
            if eff_before < 1:
                resistances_before.append(attacking_type)
            if eff_after < 1:
                resistances_after.append(attacking_type)

        # Check for weakness elimination
        eliminated_weaknesses = [t for t in weaknesses_before if t not in weaknesses_after]
        new_weaknesses = [t for t in weaknesses_after if t not in weaknesses_before]

        if eliminated_weaknesses:
            defensive_benefits.append({
                "benefit": f"消除弱点: {', '.join(eliminated_weaknesses)}",
                "impact": "positive",
            })
        if new_weaknesses:
            defensive_benefits.append({
                "benefit": f"新增弱点: {', '.join(new_weaknesses)}",
                "impact": "negative",
            })

        # Calculate synergy score
        synergy_score = 0
        synergy_details = []

        # Offensive synergy
        if offensive_benefits:
            synergy_score += len(offensive_benefits) * 10
            synergy_details.append(f"获得 {len(offensive_benefits)} 个招式的 STAB 加成")

        # Defensive synergy
        if eliminated_weaknesses:
            synergy_score += len(eliminated_weaknesses) * 15
            synergy_details.append(f"消除 {len(eliminated_weaknesses)} 个弱点")
        if new_weaknesses:
            synergy_score -= len(new_weaknesses) * 10
            synergy_details.append(f"新增 {len(new_weaknesses)} 个弱点")

        # Type diversity
        if not is_same_type:
            synergy_score += 5
            synergy_details.append("太晶类型与原始类型不同，增加变化性")

        # Rating
        rating = "neutral"
        if synergy_score >= 30:
            rating = "excellent"
        elif synergy_score >= 20:
            rating = "good"
        elif synergy_score >= 10:
            rating = "fair"
        elif synergy_score < 0:
            rating = "poor"

        return {
            "tera_type": tera_type,
            "pokemon_types": pokemon_types,
            "is_same_type": is_same_type,
            "offensive_benefits": offensive_benefits,
            "defensive_benefits": defensive_benefits,
            "weaknesses_before": weaknesses_before,
            "weaknesses_after": weaknesses_after,
            "resistances_before": resistances_before,
            "resistances_after": resistances_after,
            "eliminated_weaknesses": eliminated_weaknesses,
            "new_weaknesses": new_weaknesses,
            "synergy_score": synergy_score,
            "synergy_details": synergy_details,
            "rating": rating,
        }

    def recommend_tera_type(
        self,
        pokemon_types: list[str],
        moves: list[dict[str, Any] | str] | None = None,
        ability: str | None = None,
        role: str | None = None,
        battle_format: str = "vgc2024",
    ) -> list[dict[str, Any]]:
        """Recommend Tera types for a Pokemon."""
        recommendations = []

        # Offensive recommendations
        if moves:
            move_types = set()
            for move in moves:
                if isinstance(move, dict):
                    move_type = move.get("type")
                    if move_type:
                        move_types.add(move_type)

            # Recommend Tera type matching strongest move
            for move_type in move_types:
                if move_type not in pokemon_types:
                    recommendations.append({
                        "tera_type": move_type,
                        "category": "offensive",
                        "reason": f"获得 {move_type} 属性招式的 STAB 加成",
                        "priority": "high",
                    })

        # Defensive recommendations
        # Find types that eliminate weaknesses
        weaknesses = set()
        for attacking_type in self.type_chart.types:
            eff = self.type_chart.get_dual_type_effectiveness(attacking_type, pokemon_types)
            if eff > 1:
                weaknesses.add(attacking_type)

        # Find types that resist current weaknesses
        for tera_type in self.type_chart.types:
            if tera_type in pokemon_types:
                continue
            resists_all = True
            for weakness in weaknesses:
                eff = self.type_chart.get_effectiveness(weakness, tera_type)
                if eff >= 1:
                    resists_all = False
                    break
            if resists_all and weaknesses:
                recommendations.append({
                    "tera_type": tera_type,
                    "category": "defensive",
                    "reason": f"消除所有弱点: {', '.join(weaknesses)}",
                    "priority": "high",
                })

        # Format-specific recommendations
        if battle_format.startswith("vgc"):
            # VGC commonly uses defensive Tera types
            if "Steel" not in pokemon_types:
                recommendations.append({
                    "tera_type": "Steel",
                    "category": "defensive",
                    "reason": "钢属性太晶提供大量抗性",
                    "priority": "medium",
                })
            if "Fairy" not in pokemon_types:
                recommendations.append({
                    "tera_type": "Fairy",
                    "category": "defensive",
                    "reason": "妖精属性太晶免疫龙属性",
                    "priority": "medium",
                })

        # Remove duplicates
        seen = set()
        filtered = []
        for rec in recommendations:
            if rec["tera_type"] not in seen:
                seen.add(rec["tera_type"])
                filtered.append(rec)

        return filtered[:5]

    def get_all_tera_types(self) -> list[dict[str, Any]]:
        """Get all Tera type categories."""
        return [
            {
                "category": cat_name,
                "description": cat_def["description"],
                "purpose": cat_def["purpose"],
                "types": cat_def["types"],
            }
            for cat_name, cat_def in TERA_CATEGORIES.items()
        ]


pokemon_tera_analysis = PokemonTeraAnalysis()
