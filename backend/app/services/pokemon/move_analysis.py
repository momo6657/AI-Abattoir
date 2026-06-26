"""Pokemon move analysis service.

Provides move effectiveness calculations, coverage analysis,
and strategic move recommendations.
"""

from __future__ import annotations

from typing import Any

from app.services.pokemon.type_chart import TypeChart


# Move category priorities for strategic analysis
PRIORITY_MOVES = {
    "extreme speed": 2,
    "fake out": 3,
    "bullet punch": 1,
    "aqua jet": 1,
    "ice shard": 1,
    "shadow sneak": 1,
    "sucker punch": 1,
    "quick attack": 1,
}


class PokemonMoveAnalysis:
    """Analyzes Pokemon moves for strategic value."""

    def __init__(self):
        self.type_chart = TypeChart()

    def analyze_moveset(
        self,
        moves: list[dict[str, Any] | str],
        pokemon_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze a Pokemon's moveset for coverage and utility."""
        if not moves:
            return {"error": "No moves provided", "score": 0}

        analysis = {
            "move_count": len(moves),
            "type_coverage": self._analyze_type_coverage(moves),
            "category_balance": self._analyze_category_balance(moves),
            "priority_moves": self._find_priority_moves(moves),
            "stab_moves": self._find_stab_moves(moves, pokemon_types or []),
            "utility_moves": self._find_utility_moves(moves),
            "score": 0,
        }

        # Calculate score
        score = 0
        score += min(30, analysis["type_coverage"]["coverage_percent"] * 0.3)
        score += min(20, analysis["category_balance"]["balance_score"])
        score += min(15, len(analysis["priority_moves"]) * 5)
        score += min(15, len(analysis["stab_moves"]) * 5)
        score += min(20, len(analysis["utility_moves"]) * 4)
        analysis["score"] = min(100, score)

        return analysis

    def _analyze_type_coverage(self, moves: list[dict[str, Any] | str]) -> dict[str, Any]:
        """Analyze which types this moveset can hit effectively."""
        covered_types: set[str] = set()
        move_types: list[str] = []

        for move in moves:
            move_type = None
            if isinstance(move, dict):
                move_type = move.get("type")
            elif isinstance(move, str):
                # Simple type inference from common moves
                move_type = self._infer_move_type(move)

            if move_type:
                move_types.append(move_type)
                for defending_type in self.type_chart.types:
                    eff = self.type_chart.get_effectiveness(move_type, defending_type)
                    if eff > 1:
                        covered_types.add(defending_type)

        total_types = len(self.type_chart.types)
        return {
            "covered_types": list(covered_types),
            "uncovered_types": [t for t in self.type_chart.types if t not in covered_types],
            "coverage_percent": round(len(covered_types) / total_types * 100) if total_types else 0,
            "move_types": move_types,
        }

    def _analyze_category_balance(self, moves: list[dict[str, Any] | str]) -> dict[str, Any]:
        """Analyze physical/special/status move balance."""
        physical = 0
        special = 0
        status = 0

        for move in moves:
            if isinstance(move, dict):
                category = move.get("category", "").lower()
                if category == "physical":
                    physical += 1
                elif category == "special":
                    special += 1
                elif category == "status":
                    status += 1

        total = physical + special + status
        balance_score = 0

        # Good balance: at least 1 physical and 1 special, or all attacking
        if physical > 0 and special > 0:
            balance_score = 20
        elif physical > 0 or special > 0:
            balance_score = 10
        if status > 0 and status <= 2:
            balance_score += 5

        return {
            "physical": physical,
            "special": special,
            "status": status,
            "total": total,
            "balance_score": min(20, balance_score),
        }

    def _find_priority_moves(self, moves: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
        """Find priority moves in the moveset."""
        priority_moves = []
        for move in moves:
            name = ""
            if isinstance(move, dict):
                name = move.get("name", "").lower()
                priority = move.get("priority", 0)
                if priority > 0:
                    priority_moves.append({
                        "name": name,
                        "priority": priority,
                        "type": move.get("type"),
                    })
            elif isinstance(move, str):
                name = move.lower()
                if name in PRIORITY_MOVES:
                    priority_moves.append({
                        "name": name,
                        "priority": PRIORITY_MOVES[name],
                    })
        return priority_moves

    def _find_stab_moves(
        self,
        moves: list[dict[str, Any] | str],
        pokemon_types: list[str],
    ) -> list[dict[str, Any]]:
        """Find Same-Type Attack Bonus (STAB) moves."""
        stab_moves = []
        for move in moves:
            move_type = None
            name = ""
            if isinstance(move, dict):
                move_type = move.get("type")
                name = move.get("name", "")
            elif isinstance(move, str):
                move_type = self._infer_move_type(move)
                name = move

            if move_type and move_type in pokemon_types:
                stab_moves.append({
                    "name": name,
                    "type": move_type,
                    "stab_bonus": 1.5,
                })
        return stab_moves

    def _find_utility_moves(self, moves: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
        """Find utility/status moves."""
        utility_keywords = [
            "protect", "detect", "substitute", "rest", "sleep talk",
            "wish", "heal bell", "aromatherapy", "defog", "rapid spin",
            "taunt", "encore", "trick", "switcheroo", "knock off",
            "stealth rock", "spikes", "toxic spikes", "sticky web",
            "tailwind", "trick room", "rain dance", "sunny day",
            "thunder wave", "will-o-wisp", "toxic", "hypnosis",
        ]

        utility_moves = []
        for move in moves:
            name = ""
            if isinstance(move, dict):
                name = move.get("name", "").lower()
                category = move.get("category", "").lower()
                if category == "status":
                    utility_moves.append({
                        "name": name,
                        "category": "status",
                    })
            elif isinstance(move, str):
                name = move.lower()
                if any(kw in name for kw in utility_keywords):
                    utility_moves.append({
                        "name": name,
                        "category": "utility",
                    })
        return utility_moves

    def _infer_move_type(self, move_name: str) -> str | None:
        """Infer move type from common move names."""
        move_name = move_name.lower()
        type_moves = {
            "Normal": ["tackle", "scratch", "quick attack", "extreme speed", "body slam", "return"],
            "Fire": ["flamethrower", "fire blast", "heat wave", "overheat", "fire punch", "ember"],
            "Water": ["surf", "hydro pump", "waterfall", "scald", "aqua jet", "liquidation"],
            "Grass": ["leaf blade", "energy ball", "giga drain", "solar beam", "power whip"],
            "Electric": ["thunderbolt", "thunder", "volt switch", "wild charge", "thunder punch"],
            "Ice": ["ice beam", "blizzard", "ice punch", "icicle crash", "ice shard"],
            "Fighting": ["close combat", "focus blast", "aura sphere", "brick break", "drain punch"],
            "Poison": ["sludge bomb", "gunk shot", "poison jab", "toxic"],
            "Ground": ["earthquake", "earth power", "dig", "stomping tantrum"],
            "Flying": ["brave bird", "hurricane", "air slash", "acrobatics", "dual wingbeat"],
            "Psychic": ["psychic", "psyshock", "zen headbutt", "psycho boost"],
            "Bug": ["u-turn", "x-scissor", "bug buzz", "megahorn", "leech life"],
            "Rock": ["rock slide", "stone edge", "rock blast", "stealth rock"],
            "Ghost": ["shadow ball", "shadow claw", "poltergeist", "shadow sneak"],
            "Dragon": ["draco meteor", "dragon claw", "dragon pulse", "outrage"],
            "Dark": ["knock off", "sucker punch", "crunch", "dark pulse", "foul play"],
            "Steel": ["iron head", "flash cannon", "bullet punch", "meteor mash"],
            "Fairy": ["moonblast", "play rough", "dazzling gleam", "fairy wind"],
        }

        for type_name, moves in type_moves.items():
            if move_name in moves:
                return type_name
        return None


pokemon_move_analysis = PokemonMoveAnalysis()
