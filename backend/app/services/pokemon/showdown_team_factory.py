"""Showdown-ready team generation for autonomous sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.pokemon.format_catalog import pokemon_format_catalog
from app.services.pokemon.team_builder import pokemon_team_builder


@dataclass
class GeneratedShowdownTeam:
    team: list[dict[str, Any]]
    source: str
    reason: str
    adjustments: list[dict[str, str]] = field(default_factory=list)

    def species(self) -> list[str]:
        return [str(member.get("species") or member.get("name") or "Unknown") for member in self.team]


class PokemonShowdownTeamFactory:
    """Builds fallback Showdown teams when a session has no user-provided team."""

    def generate(
        self,
        battle_format: str,
        *,
        mode: str = "balanced",
        learning_profile: dict[str, Any] | None = None,
    ) -> GeneratedShowdownTeam | None:
        format_info = pokemon_format_catalog.get(battle_format)
        if not format_info.requires_team:
            return None
        if format_info.template_format:
            team = self._template_team(format_info.id, mode)
            return self._with_learning_adjustments(
                team=team[:format_info.team_size],
                source="template",
                reason=f"Selected a {mode} local template for {format_info.name}.",
                battle_type=format_info.battle_type,
                learning_profile=learning_profile,
            )
        if format_info.battle_type == "double":
            return self._with_learning_adjustments(
                team=self._doubles_showdown_team(),
                source="showdown_factory",
                reason=f"Generated a stable doubles team for {format_info.name}.",
                battle_type=format_info.battle_type,
                learning_profile=learning_profile,
            )
        return self._with_learning_adjustments(
            team=self._singles_showdown_team(),
            source="showdown_factory",
            reason=f"Generated a stable singles team for {format_info.name}.",
            battle_type=format_info.battle_type,
            learning_profile=learning_profile,
        )

    def _template_team(self, battle_format: str, mode: str) -> list[dict[str, Any]]:
        templates = pokemon_team_builder.load_templates(battle_format)
        if not templates:
            raise ValueError(f"No Pokemon team templates for format: {battle_format}")
        mode_keywords = {
            "aggressive": ["sun", "tailwind", "good"],
            "defensive": ["trick", "rain", "good"],
            "balanced": ["good", "tailwind", "rain"],
        }
        for keyword in mode_keywords.get(mode, mode_keywords["balanced"]):
            template = self._find_template(templates, keyword)
            if template:
                return [self._copy_member(member) for member in template["pokemon"]]
        return [self._copy_member(member) for member in templates[0]["pokemon"]]

    def _copy_member(self, member: dict[str, Any]) -> dict[str, Any]:
        copied = dict(member)
        copied["moves"] = list(member.get("moves") or [])
        copied["evs"] = dict(member.get("evs") or {})
        copied["ivs"] = dict(member.get("ivs") or {})
        return copied

    def _find_template(self, templates: list[dict[str, Any]], keyword: str) -> dict[str, Any] | None:
        for template in templates:
            haystack = f"{template.get('id', '')} {template.get('name', '')} {template.get('description', '')}".lower()
            if keyword in haystack:
                return template
        return None

    def _with_learning_adjustments(
        self,
        *,
        team: list[dict[str, Any]],
        source: str,
        reason: str,
        battle_type: str,
        learning_profile: dict[str, Any] | None,
    ) -> GeneratedShowdownTeam:
        adjustments = self._learning_adjustments(team, battle_type, learning_profile)
        if adjustments:
            source = f"learned_{source}"
            reason = f"{reason} Applied learned safety adjustments from the current Showdown profile."
        return GeneratedShowdownTeam(team=team, source=source, reason=reason, adjustments=adjustments)

    def _learning_adjustments(
        self,
        team: list[dict[str, Any]],
        battle_type: str,
        learning_profile: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        if not learning_profile or int(learning_profile.get("battles") or 0) <= 0:
            return []

        adjustments: list[dict[str, str]] = []
        win_rate = float(learning_profile.get("win_rate") or 0.0)
        average_reward = float(learning_profile.get("average_reward") or 0.0)
        faints_for = int(learning_profile.get("faints_for") or 0)
        faints_against = int(learning_profile.get("faints_against") or 0)
        needs_safety = win_rate < 0.5 or average_reward < 50 or faints_against > faints_for

        if needs_safety and battle_type == "double":
            protected = self._add_protect_to_vulnerable_members(team, limit=2)
            if protected:
                adjustments.append(
                    {
                        "type": "move",
                        "title": "Added Protect safety",
                        "detail": f"Added Protect to {', '.join(protected)} after weak Showdown results.",
                    }
                )
        if needs_safety:
            changed = self._soften_high_risk_items(team)
            if changed:
                adjustments.append(
                    {
                        "type": "item",
                        "title": "Reduced item risk",
                        "detail": f"Changed high-risk item(s) on {', '.join(changed)} for more stable ladder runs.",
                    }
                )
        return adjustments

    def _add_protect_to_vulnerable_members(self, team: list[dict[str, Any]], *, limit: int) -> list[str]:
        core_moves = {"fake out", "tailwind", "trick room", "spore", "rage powder", "follow me", "protect"}
        changed: list[str] = []
        for member in team:
            moves = list(member.get("moves") or [])
            if len(changed) >= limit or not moves or any(str(move).lower() == "protect" for move in moves):
                continue
            replace_index = len(moves) - 1
            for index in range(len(moves) - 1, -1, -1):
                if str(moves[index]).lower() not in core_moves:
                    replace_index = index
                    break
            moves[replace_index] = "Protect"
            member["moves"] = moves
            changed.append(str(member.get("species") or member.get("name") or "Unknown"))
        return changed

    def _soften_high_risk_items(self, team: list[dict[str, Any]]) -> list[str]:
        replacements = {
            "Life Orb": "Sitrus Berry",
            "Choice Band": "Assault Vest",
            "Choice Specs": "Focus Sash",
        }
        changed: list[str] = []
        for member in team:
            item = str(member.get("item") or "")
            if item not in replacements:
                continue
            member["item"] = replacements[item]
            changed.append(str(member.get("species") or member.get("name") or "Unknown"))
            if len(changed) >= 2:
                break
        return changed

    def _singles_showdown_team(self) -> list[dict[str, Any]]:
        return [
            {
                "species": "Great Tusk",
                "ability": "Protosynthesis",
                "item": "Booster Energy",
                "moves": ["Headlong Rush", "Close Combat", "Rapid Spin", "Knock Off"],
                "nature": "Jolly",
                "evs": {"atk": 252, "spd": 4, "spe": 252},
                "level": 100,
                "tera_type": "Ground",
            },
            {
                "species": "Kingambit",
                "ability": "Supreme Overlord",
                "item": "Black Glasses",
                "moves": ["Kowtow Cleave", "Sucker Punch", "Iron Head", "Swords Dance"],
                "nature": "Adamant",
                "evs": {"hp": 252, "atk": 252, "spd": 4},
                "level": 100,
                "tera_type": "Dark",
            },
            {
                "species": "Gholdengo",
                "ability": "Good as Gold",
                "item": "Choice Scarf",
                "moves": ["Make It Rain", "Shadow Ball", "Focus Blast", "Trick"],
                "nature": "Timid",
                "evs": {"spa": 252, "spd": 4, "spe": 252},
                "level": 100,
                "tera_type": "Steel",
            },
            {
                "species": "Dragapult",
                "ability": "Infiltrator",
                "item": "Choice Specs",
                "moves": ["Draco Meteor", "Shadow Ball", "Flamethrower", "U-turn"],
                "nature": "Timid",
                "evs": {"spa": 252, "spd": 4, "spe": 252},
                "level": 100,
                "tera_type": "Ghost",
            },
            {
                "species": "Iron Valiant",
                "ability": "Quark Drive",
                "item": "Booster Energy",
                "moves": ["Moonblast", "Close Combat", "Knock Off", "Encore"],
                "nature": "Naive",
                "evs": {"atk": 4, "spa": 252, "spe": 252},
                "level": 100,
                "tera_type": "Fairy",
            },
            {
                "species": "Ting-Lu",
                "ability": "Vessel of Ruin",
                "item": "Leftovers",
                "moves": ["Earthquake", "Ruination", "Stealth Rock", "Whirlwind"],
                "nature": "Careful",
                "evs": {"hp": 252, "def": 4, "spd": 252},
                "level": 100,
                "tera_type": "Water",
            },
        ]

    def _doubles_showdown_team(self) -> list[dict[str, Any]]:
        return [
            {
                "species": "Incineroar",
                "ability": "Intimidate",
                "item": "Sitrus Berry",
                "moves": ["Fake Out", "Flare Blitz", "Parting Shot", "Knock Off"],
                "nature": "Careful",
                "evs": {"hp": 252, "def": 4, "spd": 252},
                "level": 100,
                "tera_type": "Grass",
            },
            {
                "species": "Rillaboom",
                "ability": "Grassy Surge",
                "item": "Assault Vest",
                "moves": ["Fake Out", "Grassy Glide", "Wood Hammer", "U-turn"],
                "nature": "Adamant",
                "evs": {"hp": 252, "atk": 252, "def": 4},
                "level": 100,
                "tera_type": "Fire",
            },
            {
                "species": "Flutter Mane",
                "ability": "Protosynthesis",
                "item": "Booster Energy",
                "moves": ["Moonblast", "Shadow Ball", "Icy Wind", "Protect"],
                "nature": "Timid",
                "evs": {"hp": 4, "spa": 252, "spe": 252},
                "level": 100,
                "tera_type": "Fairy",
            },
            {
                "species": "Urshifu-Rapid-Strike",
                "ability": "Unseen Fist",
                "item": "Mystic Water",
                "moves": ["Surging Strikes", "Close Combat", "Aqua Jet", "Protect"],
                "nature": "Adamant",
                "evs": {"hp": 4, "atk": 252, "spe": 252},
                "level": 100,
                "tera_type": "Water",
            },
            {
                "species": "Tornadus",
                "ability": "Prankster",
                "item": "Covert Cloak",
                "moves": ["Tailwind", "Bleakwind Storm", "Taunt", "Protect"],
                "nature": "Timid",
                "evs": {"hp": 4, "spa": 252, "spe": 252},
                "level": 100,
                "tera_type": "Steel",
            },
            {
                "species": "Gholdengo",
                "ability": "Good as Gold",
                "item": "Life Orb",
                "moves": ["Make It Rain", "Shadow Ball", "Nasty Plot", "Protect"],
                "nature": "Timid",
                "evs": {"hp": 4, "spa": 252, "spe": 252},
                "level": 100,
                "tera_type": "Steel",
            },
        ]


pokemon_showdown_team_factory = PokemonShowdownTeamFactory()
