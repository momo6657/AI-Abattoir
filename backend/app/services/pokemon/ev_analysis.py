"""Pokemon EV (Effort Value) and IV (Individual Value) analysis service.

Provides EV/IV optimization recommendations based on
Pokemon roles and battle strategies.
"""

from __future__ import annotations

from typing import Any


# EV spreads for common roles
EV_SPREADS = {
    "physical_sweeper": {
        "description": "物攻手努力值分配",
        "recommended": {
            "hp": 4,
            "atk": 252,
            "def": 0,
            "spa": 0,
            "spd": 0,
            "spe": 252,
        },
        "nature": "adamant",
        "alternatives": [
            {"hp": 4, "atk": 252, "spe": 252, "nature": "jolly", "reason": "速度优先"},
        ],
    },
    "special_sweeper": {
        "description": "特攻手努力值分配",
        "recommended": {
            "hp": 4,
            "atk": 0,
            "def": 0,
            "spa": 252,
            "spd": 0,
            "spe": 252,
        },
        "nature": "modest",
        "alternatives": [
            {"hp": 4, "spa": 252, "spe": 252, "nature": "timid", "reason": "速度优先"},
        ],
    },
    "physical_wall": {
        "description": "物防墙努力值分配",
        "recommended": {
            "hp": 252,
            "atk": 0,
            "def": 252,
            "spa": 0,
            "spd": 4,
            "spe": 0,
        },
        "nature": "impish",
        "alternatives": [
            {"hp": 252, "def": 252, "spd": 4, "nature": "bold", "reason": "纯防御"},
        ],
    },
    "special_wall": {
        "description": "特防墙努力值分配",
        "recommended": {
            "hp": 252,
            "atk": 0,
            "def": 4,
            "spa": 0,
            "spd": 252,
            "spe": 0,
        },
        "nature": "calm",
        "alternatives": [
            {"hp": 252, "def": 4, "spd": 252, "nature": "careful", "reason": "特防优先"},
        ],
    },
    "mixed_tank": {
        "description": "双防坦克努力值分配",
        "recommended": {
            "hp": 252,
            "atk": 0,
            "def": 128,
            "spa": 0,
            "spd": 128,
            "spe": 0,
        },
        "nature": "sassy",
        "alternatives": [
            {"hp": 252, "def": 128, "spd": 128, "nature": "relaxed", "reason": "物防优先"},
        ],
    },
    "trick_room": {
        "description": "空间手努力值分配",
        "recommended": {
            "hp": 252,
            "atk": 0,
            "def": 0,
            "spa": 252,
            "spd": 4,
            "spe": 0,
        },
        "nature": "quiet",
        "alternatives": [
            {"hp": 252, "atk": 252, "def": 4, "nature": "brave", "reason": "物攻空间手"},
        ],
    },
    "bulky_attacker": {
        "description": "耐久攻击手努力值分配",
        "recommended": {
            "hp": 252,
            "atk": 252,
            "def": 0,
            "spa": 0,
            "spd": 4,
            "spe": 0,
        },
        "nature": "adamant",
        "alternatives": [
            {"hp": 252, "spa": 252, "spd": 4, "nature": "modest", "reason": "特攻耐久手"},
        ],
    },
    "fast_support": {
        "description": "高速辅助努力值分配",
        "recommended": {
            "hp": 4,
            "atk": 0,
            "def": 0,
            "spa": 0,
            "spd": 252,
            "spe": 252,
        },
        "nature": "timid",
        "alternatives": [
            {"hp": 252, "spd": 252, "spe": 4, "nature": "calm", "reason": "耐久辅助"},
        ],
    },
}


class PokemonEVAnalysis:
    """Analyzes Pokemon EV/IV distributions for optimization."""

    def analyze_ev_spread(
        self,
        evs: dict[str, int],
        nature: str,
        base_stats: dict[str, int] | None = None,
        level: int = 50,
    ) -> dict[str, Any]:
        """Analyze an EV spread for optimization."""
        # Validate EV total
        total_evs = sum(evs.values())
        max_evs = 510
        remaining = max_evs - total_evs

        # Check individual EV limits
        issues = []
        for stat, value in evs.items():
            if value > 252:
                issues.append(f"{stat} EV 超过 252 上限")
            if value < 0:
                issues.append(f"{stat} EV 不能为负数")

        # Determine role from EV distribution
        detected_role = self._detect_role(evs, nature)

        # Calculate final stats if base stats provided
        final_stats = {}
        if base_stats:
            nature_mod = self._get_nature_modifier(nature)
            for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
                base = base_stats.get(stat, 0)
                ev = evs.get(stat, 0)
                iv = 31  # Assume perfect IVs

                if stat == "hp":
                    if base == 1:  # Shedinja
                        final_stats[stat] = 1
                    else:
                        final_stats[stat] = int(((2 * base + iv + ev // 4) * level / 100) + level + 10)
                else:
                    modifier = nature_mod.get(stat, 1.0)
                    final_stats[stat] = int((((2 * base + iv + ev // 4) * level / 100) + 5) * modifier)

        # Optimization suggestions
        suggestions = []
        if detected_role and detected_role in EV_SPREADS:
            recommended = EV_SPREADS[detected_role]["recommended"]
            for stat, value in evs.items():
                rec_value = recommended.get(stat, 0)
                if abs(value - rec_value) > 20:
                    suggestions.append(f"{stat}: 建议 {rec_value} (当前 {value})")

        # Efficiency rating
        efficiency = "good"
        if total_evs > 508:
            efficiency = "excellent"
        elif total_evs < 500:
            efficiency = "suboptimal"
        if issues:
            efficiency = "invalid"

        return {
            "evs": evs,
            "total": total_evs,
            "remaining": remaining,
            "nature": nature,
            "detected_role": detected_role,
            "role_description": EV_SPREADS.get(detected_role, {}).get("description", "未知角色"),
            "final_stats": final_stats,
            "issues": issues,
            "suggestions": suggestions,
            "efficiency": efficiency,
        }

    def recommend_ev_spread(
        self,
        role: str,
        base_stats: dict[str, int] | None = None,
        battle_format: str = "vgc2024",
    ) -> dict[str, Any]:
        """Recommend an EV spread for a role."""
        if role not in EV_SPREADS:
            return {
                "error": f"Unknown role: {role}",
                "available_roles": list(EV_SPREADS.keys()),
            }

        spread = EV_SPREADS[role]

        # Adjust for base stats if provided
        recommended = spread["recommended"].copy()
        if base_stats:
            # Speed optimization
            if role in ["physical_sweeper", "special_sweeper", "fast_support"]:
                base_spe = base_stats.get("spe", 0)
                if base_spe >= 100:
                    # Fast Pokemon can invest less in speed
                    pass  # Keep max speed investment
                elif base_spe < 70:
                    # Slow Pokemon might need more speed investment
                    pass  # Keep max speed investment

            # Bulk optimization
            if role in ["physical_wall", "special_wall", "mixed_tank"]:
                base_hp = base_stats.get("hp", 0)
                if base_hp >= 100:
                    # High HP can invest more in defenses
                    pass  # Keep current distribution

        return {
            "role": role,
            "description": spread["description"],
            "recommended": recommended,
            "nature": spread["nature"],
            "alternatives": spread["alternatives"],
            "total_evs": sum(recommended.values()),
        }

    def _detect_role(self, evs: dict[str, int], nature: str) -> str:
        """Detect the role from EV distribution."""
        atk = evs.get("atk", 0)
        spa = evs.get("spa", 0)
        spe = evs.get("spe", 0)
        def_ = evs.get("def", 0)
        spd = evs.get("spd", 0)
        hp = evs.get("hp", 0)

        # Check for Trick Room (low speed investment)
        if spe == 0 and (atk >= 252 or spa >= 252) and hp >= 252:
            return "trick_room"

        # Check for sweepers
        if atk >= 252 and spe >= 252:
            return "physical_sweeper"
        if spa >= 252 and spe >= 252:
            return "special_sweeper"

        # Check for walls
        if hp >= 252 and def_ >= 252:
            return "physical_wall"
        if hp >= 252 and spd >= 252:
            return "special_wall"

        # Check for mixed tank
        if hp >= 252 and def_ >= 128 and spd >= 128:
            return "mixed_tank"

        # Check for bulky attacker
        if hp >= 252 and (atk >= 252 or spa >= 252):
            return "bulky_attacker"

        # Check for fast support
        if spe >= 252 and (spd >= 252 or def_ >= 252):
            return "fast_support"

        return "unknown"

    def _get_nature_modifier(self, nature: str) -> dict[str, float]:
        """Get stat modifiers from nature."""
        from app.services.pokemon.nature_analysis import NATURE_MODIFIERS

        modifiers = NATURE_MODIFIERS.get(nature.lower(), {})
        result = {
            "hp": 1.0,
            "atk": 1.0,
            "def": 1.0,
            "spa": 1.0,
            "spd": 1.0,
            "spe": 1.0,
        }

        if modifiers.get("increased"):
            result[modifiers["increased"]] = 1.1
        if modifiers.get("decreased"):
            result[modifiers["decreased"]] = 0.9

        return result

    def get_all_roles(self) -> list[dict[str, Any]]:
        """Get all EV spread roles."""
        return [
            {
                "role": role,
                "description": data["description"],
                "recommended": data["recommended"],
                "nature": data["nature"],
            }
            for role, data in EV_SPREADS.items()
        ]


pokemon_ev_analysis = PokemonEVAnalysis()
