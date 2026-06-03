"""Showdown-ready team generation for autonomous sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.pokemon.format_catalog import pokemon_format_catalog
from app.services.pokemon.team_builder import pokemon_team_builder


@dataclass
class GeneratedShowdownTeam:
    team: list[dict[str, Any]]
    source: str
    reason: str

    def species(self) -> list[str]:
        return [str(member.get("species") or member.get("name") or "Unknown") for member in self.team]


class PokemonShowdownTeamFactory:
    """Builds fallback Showdown teams when a session has no user-provided team."""

    def generate(self, battle_format: str, *, mode: str = "balanced") -> GeneratedShowdownTeam | None:
        format_info = pokemon_format_catalog.get(battle_format)
        if not format_info.requires_team:
            return None
        if format_info.template_format:
            team = self._template_team(format_info.id, mode)
            return GeneratedShowdownTeam(
                team=team[:format_info.team_size],
                source="template",
                reason=f"Selected a {mode} local template for {format_info.name}.",
            )
        if format_info.battle_type == "double":
            return GeneratedShowdownTeam(
                team=self._doubles_showdown_team(),
                source="showdown_factory",
                reason=f"Generated a stable doubles team for {format_info.name}.",
            )
        return GeneratedShowdownTeam(
            team=self._singles_showdown_team(),
            source="showdown_factory",
            reason=f"Generated a stable singles team for {format_info.name}.",
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
                return [dict(member) for member in template["pokemon"]]
        return [dict(member) for member in templates[0]["pokemon"]]

    def _find_template(self, templates: list[dict[str, Any]], keyword: str) -> dict[str, Any] | None:
        for template in templates:
            haystack = f"{template.get('id', '')} {template.get('name', '')} {template.get('description', '')}".lower()
            if keyword in haystack:
                return template
        return None

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
