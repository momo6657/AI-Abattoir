"""Pokemon comprehensive analysis service.

Integrates all analysis services into a single comprehensive
analysis for Pokemon, teams, and battles.
"""

from __future__ import annotations

from typing import Any

from app.services.pokemon.type_chart import TypeChart
from app.services.pokemon.team_analysis import pokemon_team_analysis
from app.services.pokemon.move_analysis import pokemon_move_analysis
from app.services.pokemon.item_analysis import pokemon_item_analysis
from app.services.pokemon.ability_analysis import pokemon_ability_analysis
from app.services.pokemon.nature_analysis import pokemon_nature_analysis
from app.services.pokemon.ev_analysis import pokemon_ev_analysis
from app.services.pokemon.tera_analysis import pokemon_tera_analysis


class PokemonComprehensiveAnalysis:
    """Provides comprehensive analysis combining all analysis services."""

    def analyze_pokemon(
        self,
        pokemon: dict[str, Any],
        battle_format: str = "vgc2024",
    ) -> dict[str, Any]:
        """Perform comprehensive analysis on a single Pokemon."""
        species = pokemon.get("species") or pokemon.get("name", "Unknown")
        types = pokemon.get("types") or []
        moves = pokemon.get("moves", [])
        ability = pokemon.get("ability", "")
        item = pokemon.get("item", "")
        nature = pokemon.get("nature")
        evs = pokemon.get("evs", {})
        tera_type = pokemon.get("tera_type")
        base_stats = pokemon.get("base_stats")

        # Analyze each aspect
        moveset_analysis = pokemon_move_analysis.analyze_moveset(moves, types)
        ability_analysis = pokemon_ability_analysis.analyze_ability(ability, types, [m if isinstance(m, str) else m.get("name", "") for m in moves]) if ability else None
        nature_analysis = pokemon_nature_analysis.analyze_nature(nature, types, base_stats) if nature else None
        ev_analysis = pokemon_ev_analysis.analyze_ev_spread(evs, nature or "hardy", base_stats) if evs else None
        tera_analysis = pokemon_tera_analysis.analyze_tera_type(tera_type, types, moves, ability) if tera_type else None

        # Only score dimensions backed by actual input data.
        scores: list[Any] = [moveset_analysis.get("score", 0)]
        if ability_analysis:
            scores.append(ability_analysis.get("synergy_score", 0))
        if nature_analysis:
            scores.append(nature_analysis.get("synergy_score", 0))
        if ev_analysis:
            scores.append(ev_analysis.get("efficiency", 0))
        if tera_analysis:
            scores.append(tera_analysis.get("synergy_score", 0))
        normalized_scores = [self._normalize_score(score) for score in scores]

        overall_score = sum(normalized_scores) / len(normalized_scores) if normalized_scores else 0

        # Generate recommendations
        recommendations = []
        if moveset_analysis.get("score", 0) < 50:
            recommendations.append("考虑优化招式搭配以提高属性覆盖")
        if ability_analysis and ability_analysis.get("rating") == "low":
            recommendations.append("考虑更换特性以获得更好的协同效果")
        if nature_analysis and nature_analysis.get("rating") == "neutral":
            recommendations.append("考虑调整性格以匹配宝可梦的角色定位")
        if ev_analysis and ev_analysis.get("efficiency") == "suboptimal":
            recommendations.append("优化努力值分配以提高战斗效率")
        if tera_analysis and tera_analysis.get("rating") == "poor":
            recommendations.append("重新考虑太晶属性选择")

        return {
            "species": species,
            "types": types,
            "overall_score": round(overall_score),
            "rating": self._score_to_rating(overall_score),
            "analyses": {
                "moveset": moveset_analysis,
                "ability": ability_analysis,
                "nature": nature_analysis,
                "evs": ev_analysis,
                "tera": tera_analysis,
            },
            "recommendations": recommendations,
            "battle_format": battle_format,
            "data_completeness": {
                "types": bool(types),
                "ability": bool(ability),
                "nature": bool(nature),
                "evs": bool(evs),
                "tera_type": bool(tera_type),
                "base_stats": bool(base_stats),
            },
        }

    def analyze_team_comprehensive(
        self,
        team: list[dict[str, Any]],
        battle_format: str = "vgc2024",
    ) -> dict[str, Any]:
        """Perform comprehensive analysis on a team."""
        # Team composition analysis
        team_analysis = pokemon_team_analysis.analyze_team(team, battle_format)

        # Individual Pokemon analyses
        pokemon_analyses = []
        for pokemon in team:
            analysis = self.analyze_pokemon(pokemon, battle_format)
            pokemon_analyses.append(analysis)

        # Team synergy analysis
        synergy_score = self._analyze_team_synergy(team)

        # Format compatibility
        format_compatibility = self._analyze_format_compatibility(team, battle_format)

        # Calculate overall team score
        team_score = team_analysis.get("score", 0)
        avg_pokemon_score = sum(a.get("overall_score", 0) for a in pokemon_analyses) / len(pokemon_analyses) if pokemon_analyses else 0
        overall_score = (team_score * 0.4 + avg_pokemon_score * 0.3 + synergy_score * 0.3)

        # Generate team recommendations
        recommendations = team_analysis.get("recommendations", [])
        if synergy_score < 50:
            recommendations.append("考虑增加队伍成员之间的属性协同")
        if format_compatibility < 50:
            recommendations.append("队伍与当前格式的兼容性较低，考虑调整")

        return {
            "team_size": len(team),
            "battle_format": battle_format,
            "overall_score": round(overall_score),
            "rating": self._score_to_rating(overall_score),
            "team_analysis": team_analysis,
            "pokemon_analyses": pokemon_analyses,
            "synergy_score": synergy_score,
            "format_compatibility": format_compatibility,
            "recommendations": recommendations,
        }

    def _analyze_team_synergy(self, team: list[dict[str, Any]]) -> float:
        """Analyze synergy between team members."""
        if len(team) < 2:
            return 50

        synergy_score = 50  # Base score

        # Check type coverage
        all_types = set()
        for pokemon in team:
            types = pokemon.get("types", [])
            all_types.update(types)

        # Reward type diversity
        if len(all_types) >= 8:
            synergy_score += 20
        elif len(all_types) >= 6:
            synergy_score += 10

        # Check for complementary roles
        has_sweeper = False
        has_wall = False
        has_support = False
        for pokemon in team:
            moves = pokemon.get("moves", [])
            move_names = [m.lower() if isinstance(m, str) else m.get("name", "").lower() for m in moves]
            if any(m in move_names for m in ["swords dance", "dragon dance", "nasty plot"]):
                has_sweeper = True
            if any(m in move_names for m in ["recover", "slack off", "roost"]):
                has_wall = True
            if any(m in move_names for m in ["follow me", "rage powder", "tailwind", "trick room"]):
                has_support = True

        if has_sweeper and has_wall and has_support:
            synergy_score += 15
        elif has_sweeper and (has_wall or has_support):
            synergy_score += 10

        return min(100, synergy_score)

    def _analyze_format_compatibility(
        self,
        team: list[dict[str, Any]],
        battle_format: str,
    ) -> float:
        """Analyze how well a team fits a battle format."""
        compatibility = 50  # Base score

        if battle_format.startswith("vgc"):
            # VGC: check for Fake Out, Protect, speed control
            has_fake_out = False
            has_protect = False
            has_speed_control = False
            for pokemon in team:
                moves = pokemon.get("moves", [])
                move_names = [m.lower() if isinstance(m, str) else m.get("name", "").lower() for m in moves]
                if "fake out" in move_names:
                    has_fake_out = True
                if "protect" in move_names:
                    has_protect = True
                if any(m in move_names for m in ["tailwind", "trick room", "icy wind"]):
                    has_speed_control = True

            if has_fake_out:
                compatibility += 15
            if has_protect:
                compatibility += 15
            if has_speed_control:
                compatibility += 10

        elif battle_format in ["gen9ou", "gen9uu"]:
            # Singles: check for hazard control, hazard removal
            has_hazards = False
            has_removal = False
            for pokemon in team:
                moves = pokemon.get("moves", [])
                move_names = [m.lower() if isinstance(m, str) else m.get("name", "").lower() for m in moves]
                if "stealth rock" in move_names or "spikes" in move_names:
                    has_hazards = True
                if "rapid spin" in move_names or "defog" in move_names:
                    has_removal = True

            if has_hazards:
                compatibility += 15
            if has_removal:
                compatibility += 10

        return min(100, compatibility)

    def _score_to_rating(self, score: float) -> str:
        """Convert score to rating."""
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "good"
        elif score >= 40:
            return "fair"
        elif score >= 20:
            return "poor"
        return "very poor"

    def _normalize_score(self, score: Any) -> float:
        if isinstance(score, (int, float)):
            return max(0.0, min(100.0, float(score)))
        return {
            "excellent": 100.0,
            "optimal": 100.0,
            "good": 75.0,
            "fair": 50.0,
            "neutral": 50.0,
            "suboptimal": 30.0,
            "poor": 20.0,
            "low": 20.0,
            "invalid": 0.0,
        }.get(str(score).lower(), 0.0)


pokemon_comprehensive_analysis = PokemonComprehensiveAnalysis()
