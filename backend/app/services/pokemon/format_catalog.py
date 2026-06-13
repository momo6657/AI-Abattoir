"""Pokemon battle format catalog.

The catalog separates local training/template formats from Pokemon Showdown
format IDs so future formats can be added without spreading hard-coded strings
through team building, sessions, and UI code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PokemonBattleFormat:
    id: str
    name: str
    name_zh: str
    showdown_format: str
    battle_type: str
    generation: int
    team_size: int
    active_pokemon: int
    requires_team: bool = True
    template_format: str | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "name_zh": self.name_zh,
            "showdown_format": self.showdown_format,
            "battle_type": self.battle_type,
            "generation": self.generation,
            "team_size": self.team_size,
            "active_pokemon": self.active_pokemon,
            "requires_team": self.requires_team,
            "template_format": self.template_format,
            "description": self.description,
            "tags": self.tags,
            "strategy_profile": self.strategy_profile(),
        }

    def strategy_profile(self) -> dict[str, Any]:
        """Return a compact policy profile for format-aware autonomous choices."""
        target_policy = "targeted" if self.active_pokemon > 1 else "no_target"
        if not self.requires_team:
            archetype = "random_single"
            opening_style = "Scout the generated set, preserve HP, and convert high-value setup or damage windows."
            priorities = ["immediate_damage", "setup_when_safe", "recovery_above_chip", "avoid_blind_sacrifices"]
            risk_controls = ["do_not_assume_team_preview", "avoid_low_value_status_when_behind"]
        elif self.battle_type == "double":
            archetype = "coordinated_double"
            opening_style = "Build turn-one position with Fake Out, speed control, redirection, and spread pressure."
            priorities = ["fake_out_pressure", "speed_control", "redirection_support", "spread_damage", "protect_positioning"]
            risk_controls = ["avoid_double_targeting_into_protect", "protect_low_confidence_slots", "preserve_board_position"]
        else:
            archetype = "structured_single"
            opening_style = "Create long-term value with hazards, pivots, removal, recovery, and cleaner preservation."
            priorities = ["entry_hazards", "hazard_removal", "pivoting", "recovery", "setup_cleaner"]
            risk_controls = ["avoid_unnecessary_tera", "preserve_defensive_pivots", "do_not_trade_cleaner_early"]

        return {
            "archetype": archetype,
            "target_policy": target_policy,
            "opening_style": opening_style,
            "priorities": priorities,
            "risk_controls": risk_controls,
            "supports_team_preview": self.requires_team,
            "supports_random_sets": not self.requires_team,
        }


class PokemonFormatCatalog:
    """Maps local and Showdown format names to normalized format metadata."""

    def __init__(self):
        self._formats = [
            PokemonBattleFormat(
                id="vgc2024",
                name="VGC 2024 Regulation G",
                name_zh="VGC 2024 规则 G",
                showdown_format="gen9vgc2024regg",
                battle_type="double",
                generation=9,
                team_size=4,
                active_pokemon=2,
                template_format="vgc2024",
                description="Current local training baseline: open-team-sheet-style VGC doubles with four selected Pokemon.",
                tags=["vgc", "double", "team-preview", "local-template"],
            ),
            PokemonBattleFormat(
                id="gen9doublesou",
                name="Gen 9 Doubles OU",
                name_zh="第九世代双打 OU",
                showdown_format="gen9doublesou",
                battle_type="double",
                generation=9,
                team_size=6,
                active_pokemon=2,
                description="Smogon doubles format for broader non-VGC doubles practice.",
                tags=["double", "smogon", "showdown"],
            ),
            PokemonBattleFormat(
                id="gen9ou",
                name="Gen 9 OU",
                name_zh="第九世代单打 OU",
                showdown_format="gen9ou",
                battle_type="single",
                generation=9,
                team_size=6,
                active_pokemon=1,
                description="Standard singles ladder format for future single-battle policy work.",
                tags=["single", "smogon", "showdown"],
            ),
            PokemonBattleFormat(
                id="gen9randombattle",
                name="Gen 9 Random Battle",
                name_zh="第九世代随机战",
                showdown_format="gen9randombattle",
                battle_type="single",
                generation=9,
                team_size=6,
                active_pokemon=1,
                requires_team=False,
                description="Showdown-provided random teams; useful for testing battle policy without team building.",
                tags=["single", "random", "no-team", "showdown"],
            ),
        ]
        self._aliases = {
            "gen9vgc2024regg": "vgc2024",
            "vgc": "vgc2024",
            "vgc2024regg": "vgc2024",
            "doubles": "gen9doublesou",
            "double": "gen9doublesou",
            "singles": "gen9ou",
            "single": "gen9ou",
            "ou": "gen9ou",
            "random": "gen9randombattle",
            "randombattle": "gen9randombattle",
        }

    def list_formats(self) -> list[PokemonBattleFormat]:
        return list(self._formats)

    def get(self, format_id: str | None) -> PokemonBattleFormat:
        key = (format_id or "vgc2024").lower()
        key = self._aliases.get(key, key)
        for battle_format in self._formats:
            if battle_format.id == key or battle_format.showdown_format == key:
                return battle_format
        raise ValueError(f"Unsupported Pokemon battle format: {format_id}")

    def showdown_format(self, format_id: str | None) -> str:
        return self.get(format_id).showdown_format

    def template_format(self, format_id: str | None) -> str:
        battle_format = self.get(format_id)
        if not battle_format.template_format:
            raise ValueError(f"No local team template is configured for format: {format_id}")
        return battle_format.template_format


pokemon_format_catalog = PokemonFormatCatalog()
