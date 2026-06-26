"""Pokemon team analysis service.

Analyzes team composition, type coverage, role distribution,
and provides strategic recommendations.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.pokemon.type_chart import TypeChart
from app.services.pokemon.format_catalog import pokemon_format_catalog


# Role definitions based on common competitive archetypes
ROLES = {
    "offensive_sweeper": {
        "keywords": ["swords dance", "nasty plot", "dragon dance", "quiver dance", "shell smash"],
        "description": "进攻清场手",
    },
    "defensive_wall": {
        "keywords": ["recover", "slack off", "roost", "synthesis", "wish", "protect"],
        "description": "防御墙",
    },
    "support": {
        "keywords": ["follow me", "rage powder", "tailwind", "trick room", "helping hand", "fake out"],
        "description": "辅助支援",
    },
    "hazard_setter": {
        "keywords": ["stealth rock", "spikes", "toxic spikes", "sticky web"],
        "description": "钉子手",
    },
    "pivot": {
        "keywords": ["u-turn", "volt switch", "flip turn", "teleport", "baton pass"],
        "description": "轮转位",
    },
    "wallbreaker": {
        "keywords": ["close combat", "overheat", "draco meteor", "leaf storm", "psycho boost"],
        "description": "破盾手",
    },
    "priority_user": {
        "keywords": ["extreme speed", "bullet punch", "aqua jet", "ice shard", "shadow sneak", "sucker punch"],
        "description": "先制技能手",
    },
}


class PokemonTeamAnalysis:
    """Analyzes Pokemon team composition and provides recommendations."""

    def __init__(self):
        self.type_chart = TypeChart()

    def analyze_team(
        self,
        pokemon_list: list[dict[str, Any]],
        battle_format: str = "vgc2024",
    ) -> dict[str, Any]:
        """Analyze a team's composition and provide recommendations."""
        if not pokemon_list:
            return {"error": "Empty team", "score": 0}

        analysis = {
            "member_count": len(pokemon_list),
            "type_coverage": self._analyze_type_coverage(pokemon_list),
            "role_distribution": self._analyze_roles(pokemon_list),
            "offensive_coverage": self._analyze_offensive_coverage(pokemon_list),
            "defensive_synergy": self._analyze_defensive_synergy(pokemon_list),
            "speed_control": self._analyze_speed_control(pokemon_list),
            "recommendations": [],
            "score": 0,
        }

        # Calculate overall score
        score = 0
        score += min(20, analysis["type_coverage"]["coverage_score"])
        score += min(20, len(analysis["role_distribution"]["roles"]) * 5)
        score += min(20, analysis["offensive_coverage"]["coverage_percent"])
        score += min(20, analysis["defensive_synergy"]["synergy_score"])
        score += min(20, analysis["speed_control"]["score"])
        analysis["score"] = min(100, score)

        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis, battle_format)

        return analysis

    def _analyze_type_coverage(self, team: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze defensive type coverage."""
        all_types = set()
        weaknesses = Counter()
        resistances = Counter()

        for pokemon in team:
            types = pokemon.get("types", ["Normal"])
            all_types.update(types)

            # Count weaknesses and resistances
            for attacking_type in self.type_chart.types:
                effectiveness = self.type_chart.get_dual_type_effectiveness(attacking_type, types)
                if effectiveness > 1:
                    weaknesses[attacking_type] += 1
                elif effectiveness < 1:
                    resistances[attacking_type] += 1

        return {
            "team_types": list(all_types),
            "weaknesses": dict(weaknesses.most_common()),
            "resistances": dict(resistances.most_common()),
            "coverage_score": len(all_types) * 3,  # Simple scoring
        }

    def _analyze_roles(self, team: list[dict[str, Any]]) -> dict[str, Any]:
        """Identify team member roles based on movesets."""
        role_counts: dict[str, int] = Counter()
        member_roles: list[dict[str, Any]] = []

        for pokemon in team:
            moves = [m.lower() if isinstance(m, str) else m.get("name", "").lower() for m in pokemon.get("moves", [])]
            roles = []
            for role_name, role_def in ROLES.items():
                for keyword in role_def["keywords"]:
                    if any(keyword in move for move in moves):
                        roles.append(role_name)
                        role_counts[role_name] += 1
                        break

            member_roles.append({
                "species": pokemon.get("species") or pokemon.get("name", "Unknown"),
                "roles": roles or ["general"],
            })

        return {
            "roles": dict(role_counts),
            "member_roles": member_roles,
            "role_diversity": len(role_counts),
        }

    def _analyze_offensive_coverage(self, team: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze how many types the team can hit effectively."""
        covered_types: set[str] = set()

        for pokemon in team:
            moves = pokemon.get("moves", [])
            for move in moves:
                move_type = None
                if isinstance(move, dict):
                    move_type = move.get("type")
                elif isinstance(move, str):
                    # Try to infer type from move name (simplified)
                    continue

                if move_type:
                    # Check which types this move is super effective against
                    for defending_type in self.type_chart.types:
                        eff = self.type_chart.get_effectiveness(move_type, defending_type)
                        if eff > 1:
                            covered_types.add(defending_type)

        total_types = len(self.type_chart.types)
        return {
            "covered_types": list(covered_types),
            "uncovered_types": [t for t in self.type_chart.types if t not in covered_types],
            "coverage_percent": round(len(covered_types) / total_types * 100) if total_types else 0,
        }

    def _analyze_defensive_synergy(self, team: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze how well team members cover each other's weaknesses."""
        synergy_score = 0
        total_pairs = 0

        for i, p1 in enumerate(team):
            types1 = p1.get("types", ["Normal"])
            for j, p2 in enumerate(team):
                if j <= i:
                    continue
                types2 = p2.get("types", ["Normal"])
                total_pairs += 1

                # Check if p2 resists p1's weaknesses
                for attacking_type in self.type_chart.types:
                    eff1 = self.type_chart.get_dual_type_effectiveness(attacking_type, types1)
                    eff2 = self.type_chart.get_dual_type_effectiveness(attacking_type, types2)
                    if eff1 > 1 and eff2 < 1:
                        synergy_score += 1

        return {
            "synergy_score": min(20, synergy_score),
            "total_pairs": total_pairs,
        }

    def _analyze_speed_control(self, team: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze speed control options."""
        speed_control_moves = [
            "tailwind", "trick room", "icy wind", "electroweb",
            "sticky web", "thunder wave", "stun spore", "string shot",
        ]

        has_speed_control = False
        speed_control_users = []

        for pokemon in team:
            moves = [m.lower() if isinstance(m, str) else m.get("name", "").lower() for m in pokemon.get("moves", [])]
            for sc_move in speed_control_moves:
                if sc_move in moves:
                    has_speed_control = True
                    speed_control_users.append({
                        "species": pokemon.get("species") or pokemon.get("name", "Unknown"),
                        "move": sc_move,
                    })
                    break

        return {
            "has_speed_control": has_speed_control,
            "users": speed_control_users,
            "score": 15 if has_speed_control else 0,
        }

    def _generate_recommendations(
        self,
        analysis: dict[str, Any],
        battle_format: str,
    ) -> list[str]:
        """Generate team improvement recommendations."""
        recommendations = []

        # Check type coverage
        if analysis["type_coverage"]["coverage_score"] < 15:
            recommendations.append("考虑增加更多属性类型的宝可梦以提高属性覆盖")

        # Check role distribution
        roles = analysis["role_distribution"]["roles"]
        if "support" not in roles and battle_format.startswith("vgc"):
            recommendations.append("VGC 双打建议加入辅助型宝可梦（如 Follow Me、Tailwind 用户）")
        if not any(r in roles for r in ["offensive_sweeper", "wallbreaker"]):
            recommendations.append("队伍缺少进攻型宝可梦，可能导致输出不足")

        # Check speed control
        if not analysis["speed_control"]["has_speed_control"]:
            recommendations.append("建议加入速度控制手段（Tailwind、Trick Room 或减速技能）")

        # Check defensive synergy
        if analysis["defensive_synergy"]["synergy_score"] < 10:
            recommendations.append("队伍防御协同较弱，考虑增加属性互补的宝可梦")

        return recommendations


pokemon_team_analysis = PokemonTeamAnalysis()
