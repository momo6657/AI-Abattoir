"""Pokemon nature analysis and recommendation service.

Analyzes natures and provides recommendations based on
Pokemon roles and battle strategies.
"""

from __future__ import annotations

from typing import Any


# Nature stat modifiers
NATURE_MODIFIERS = {
    "hardy": {"increased": None, "decreased": None},
    "lonely": {"increased": "atk", "decreased": "def"},
    "brave": {"increased": "atk", "decreased": "spe"},
    "adamant": {"increased": "atk", "decreased": "spa"},
    "naughty": {"increased": "atk", "decreased": "spd"},
    "bold": {"increased": "def", "decreased": "atk"},
    "docile": {"increased": None, "decreased": None},
    "relaxed": {"increased": "def", "decreased": "spe"},
    "impish": {"increased": "def", "decreased": "spa"},
    "lax": {"increased": "def", "decreased": "spd"},
    "timid": {"increased": "spe", "decreased": "atk"},
    "hasty": {"increased": "spe", "decreased": "def"},
    "jolly": {"increased": "spe", "decreased": "spa"},
    "naive": {"increased": "spe", "decreased": "spd"},
    "modest": {"increased": "spa", "decreased": "atk"},
    "mild": {"increased": "spa", "decreased": "def"},
    "quiet": {"increased": "spa", "decreased": "spe"},
    "bashful": {"increased": None, "decreased": None},
    "rash": {"increased": "spa", "decreased": "spd"},
    "calm": {"increased": "spd", "decreased": "atk"},
    "gentle": {"increased": "spd", "decreased": "def"},
    "sassy": {"increased": "spd", "decreased": "spe"},
    "careful": {"increased": "spd", "decreased": "spa"},
    "quirky": {"increased": None, "decreased": None},
    "serious": {"increased": None, "decreased": None},
}


# Role-nature mapping
ROLE_NATURES = {
    "physical_sweeper": {
        "best": ["adamant", "jolly"],
        "good": ["lonely", "naughty", "hasty", "naive"],
        "description": "物攻手",
    },
    "special_sweeper": {
        "best": ["modest", "timid"],
        "good": ["mild", "rash", "quiet", "hasty"],
        "description": "特攻手",
    },
    "physical_wall": {
        "best": ["impish", "bold"],
        "good": ["relaxed", "lax"],
        "description": "物防墙",
    },
    "special_wall": {
        "best": ["calm", "careful"],
        "good": ["gentle", "sassy"],
        "description": "特防墙",
    },
    "mixed_attacker": {
        "best": ["naive", "hasty"],
        "good": ["lonely", "mild", "rash", "naughty"],
        "description": "双刀手",
    },
    "trick_room": {
        "best": ["brave", "quiet"],
        "good": ["relaxed", "sassy"],
        "description": "空间手",
    },
}


class PokemonNatureAnalysis:
    """Analyzes Pokemon natures for strategic value."""

    def analyze_nature(
        self,
        nature: str,
        pokemon_types: list[str] | None = None,
        base_stats: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Analyze a nature's strategic value."""
        normalized = nature.lower().strip()
        modifiers = NATURE_MODIFIERS.get(normalized)

        if not modifiers:
            return {
                "nature": nature,
                "error": f"Unknown nature: {nature}",
            }

        # Determine role suitability
        suitable_roles = []
        for role_name, role_def in ROLE_NATURES.items():
            if normalized in role_def["best"]:
                suitable_roles.append({
                    "role": role_name,
                    "description": role_def["description"],
                    "suitability": "excellent",
                })
            elif normalized in role_def["good"]:
                suitable_roles.append({
                    "role": role_name,
                    "description": role_def["description"],
                    "suitability": "good",
                })

        # Calculate stat impact
        stat_impact = {}
        if modifiers["increased"]:
            stat_impact["increased"] = {
                "stat": modifiers["increased"],
                "multiplier": 1.1,
                "description": f"{modifiers['increased'].upper()} +10%",
            }
        if modifiers["decreased"]:
            stat_impact["decreased"] = {
                "stat": modifiers["decreased"],
                "multiplier": 0.9,
                "description": f"{modifiers['decreased'].upper()} -10%",
            }

        # Synergy with base stats
        synergy_score = 0
        synergy_details = []
        if base_stats:
            if modifiers["increased"]:
                base_value = base_stats.get(modifiers["increased"], 0)
                if base_value >= 100:
                    synergy_score += 15
                    synergy_details.append(f"高{modifiers['increased'].upper()}种族值 ({base_value}) 配合加成效果好")
                elif base_value >= 80:
                    synergy_score += 10
                    synergy_details.append(f"中等{modifiers['increased'].upper()}种族值 ({base_value}) 配合加成")
            if modifiers["decreased"]:
                base_value = base_stats.get(modifiers["decreased"], 0)
                if base_value <= 60:
                    synergy_score += 10
                    synergy_details.append(f"低{modifiers['decreased'].upper()}种族值 ({base_value}) 减成影响小")
                elif base_value <= 80:
                    synergy_score += 5
                    synergy_details.append(f"中等{modifiers['decreased'].upper()}种族值 ({base_value}) 减成影响可控")

        # Rating
        rating = "neutral"
        if synergy_score >= 20:
            rating = "excellent"
        elif synergy_score >= 15:
            rating = "good"
        elif synergy_score >= 10:
            rating = "fair"

        return {
            "nature": nature,
            "modifiers": modifiers,
            "stat_impact": stat_impact,
            "suitable_roles": suitable_roles,
            "synergy_score": synergy_score,
            "synergy_details": synergy_details,
            "rating": rating,
        }

    def recommend_nature(
        self,
        pokemon_types: list[str],
        base_stats: dict[str, int] | None = None,
        role: str | None = None,
        battle_format: str = "vgc2024",
    ) -> list[dict[str, Any]]:
        """Recommend natures for a Pokemon."""
        recommendations = []

        # Determine best role if not specified
        if not role and base_stats:
            atk = base_stats.get("atk", 0)
            spa = base_stats.get("spa", 0)
            spe = base_stats.get("spe", 0)
            def_ = base_stats.get("def", 0)
            spd = base_stats.get("spd", 0)

            if atk > spa and atk > 80:
                role = "physical_sweeper"
            elif spa > atk and spa > 80:
                role = "special_sweeper"
            elif def_ > 90 or spd > 90:
                if def_ > spd:
                    role = "physical_wall"
                else:
                    role = "special_wall"
            elif spe > 100:
                role = "physical_sweeper" if atk > spa else "special_sweeper"
            else:
                role = "mixed_attacker"

        # Get recommendations based on role
        if role and role in ROLE_NATURES:
            role_def = ROLE_NATURES[role]
            for nature in role_def["best"]:
                recommendations.append({
                    "nature": nature,
                    "role": role,
                    "role_description": role_def["description"],
                    "suitability": "excellent",
                    "reason": f"{nature} 是 {role_def['description']} 的最佳性格",
                })
            for nature in role_def["good"]:
                recommendations.append({
                    "nature": nature,
                    "role": role,
                    "role_description": role_def["description"],
                    "suitability": "good",
                    "reason": f"{nature} 适合 {role_def['description']}",
                })

        # Trick Room specific
        if battle_format.startswith("vgc") and base_stats:
            spe = base_stats.get("spe", 0)
            if spe < 60:
                recommendations.append({
                    "nature": "brave",
                    "role": "trick_room",
                    "role_description": "空间手",
                    "suitability": "excellent",
                    "reason": "低速宝可梦适合空间队，Brave (+Atk -Spe) 是最佳选择",
                })
                recommendations.append({
                    "nature": "quiet",
                    "role": "trick_room",
                    "role_description": "空间手",
                    "suitability": "excellent",
                    "reason": "低速特攻手适合空间队，Quiet (+SpA -Spe) 是最佳选择",
                })

        return recommendations[:5]

    def get_all_natures(self) -> list[dict[str, Any]]:
        """Get all natures with their modifiers."""
        return [
            {
                "nature": nature,
                "increased": mods["increased"],
                "decreased": mods["decreased"],
                "is_neutral": mods["increased"] is None,
            }
            for nature, mods in NATURE_MODIFIERS.items()
        ]


pokemon_nature_analysis = PokemonNatureAnalysis()
