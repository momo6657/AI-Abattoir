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
    adjustments: list[dict[str, Any]] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)

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
            return self._finalize_team(
                team=team[:format_info.team_size],
                source="template",
                reason=f"Selected a {mode} local template for {format_info.name}.",
                format_info=format_info,
                learning_profile=learning_profile,
            )
        if format_info.battle_type == "double":
            return self._finalize_team(
                team=self._doubles_showdown_team(),
                source="showdown_factory",
                reason=f"Generated a stable doubles team for {format_info.name}.",
                format_info=format_info,
                learning_profile=learning_profile,
            )
        return self._finalize_team(
            team=self._singles_showdown_team(),
            source="showdown_factory",
            reason=f"Generated a stable singles team for {format_info.name}.",
            format_info=format_info,
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

    def _finalize_team(
        self,
        *,
        team: list[dict[str, Any]],
        source: str,
        reason: str,
        format_info: Any,
        learning_profile: dict[str, Any] | None,
    ) -> GeneratedShowdownTeam:
        adjustments = self._learning_adjustments(team, format_info.battle_type, learning_profile)
        if adjustments:
            source = f"learned_{source}"
            reason = f"{reason} Applied learned safety adjustments from the current Showdown profile."
        audit = self._build_team_audit(
            team=team,
            format_info=format_info,
            source=source,
            adjustments=adjustments,
            learning_profile=learning_profile,
        )
        return GeneratedShowdownTeam(team=team, source=source, reason=reason, adjustments=adjustments, audit=audit)

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

    def _build_team_audit(
        self,
        *,
        team: list[dict[str, Any]],
        format_info: Any,
        source: str,
        adjustments: list[dict[str, Any]],
        learning_profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        strategy_profile = format_info.strategy_profile()
        priorities = list(strategy_profile.get("priorities") or [])
        member_roles = [self._member_audit(index + 1, member) for index, member in enumerate(team)]
        present_roles = sorted({role for member in member_roles for role in member["roles"]})
        covered_priorities = [priority for priority in priorities if priority in present_roles]
        gaps = [priority for priority in priorities if priority not in present_roles]
        checks: list[dict[str, Any]] = []

        def add_check(check_id: str, status: str, detail: str) -> None:
            checks.append({"id": check_id, "status": status, "detail": detail})

        expected_size = int(format_info.team_size or len(team) or 0)
        if not team:
            add_check("team_present", "blocked", "No generated team is available for this format.")
        else:
            add_check("team_present", "passed", f"{len(team)} Pokemon are available for upload.")

        if expected_size and len(team) < expected_size:
            add_check("team_size", "blocked", f"Team has {len(team)} Pokemon but the format expects {expected_size}.")
        else:
            add_check("team_size", "passed", f"Team size matches the {format_info.name} requirement.")

        if priorities and not covered_priorities:
            add_check("format_roles", "blocked", "No generated member covers the format strategy priorities.")
        elif gaps:
            add_check("format_roles", "warning", f"Covered {len(covered_priorities)} priority role(s); gaps remain: {', '.join(gaps[:4])}.")
        else:
            add_check("format_roles", "passed", "Generated team covers the active format strategy priorities.")

        if adjustments:
            add_check("learning_adjustments", "passed", f"{len(adjustments)} learned adjustment(s) were applied.")
        elif learning_profile and int(learning_profile.get("battles") or 0) > 0:
            add_check("learning_adjustments", "warning", "Learning profile was available, but no team mutation was needed.")
        else:
            add_check("learning_adjustments", "warning", "No completed learning samples are available for team adaptation yet.")

        blocked = sum(1 for check in checks if check["status"] == "blocked")
        warnings = sum(1 for check in checks if check["status"] == "warning")
        score = max(0, 100 - blocked * 45 - warnings * 12 - len(gaps) * 3)
        if blocked:
            status = "blocked"
            recommendation = "Fix team generation before queueing this format."
        elif gaps:
            status = "warning"
            recommendation = "The team is playable, but research or later learning should cover the remaining role gaps."
        else:
            status = "passed"
            recommendation = "The generated team is aligned with the active format profile."

        return {
            "status": status,
            "score": score,
            "source": source,
            "format_id": format_info.id,
            "archetype": strategy_profile.get("archetype"),
            "expected_team_size": expected_size,
            "member_count": len(team),
            "priorities": priorities,
            "covered_priorities": covered_priorities,
            "gaps": gaps,
            "roles": present_roles,
            "member_roles": member_roles,
            "adjustment_count": len(adjustments),
            "checks": checks,
            "recommendation": recommendation,
        }

    def _member_audit(self, slot: int, member: dict[str, Any]) -> dict[str, Any]:
        move_ids = {self._to_id(move) for move in member.get("moves") or []}
        ability_id = self._to_id(member.get("ability"))
        roles: set[str] = set()
        if "fakeout" in move_ids:
            roles.add("fake_out_pressure")
        if move_ids & {"tailwind", "trickroom", "icywind", "thunderwave"}:
            roles.add("speed_control")
        if move_ids & {"followme", "ragepowder"}:
            roles.add("redirection_support")
        if move_ids & {"dazzlinggleam", "makeitrain", "heatwave", "earthquake", "rockslide", "bleakwindstorm"}:
            roles.add("spread_damage")
        if move_ids & {"protect", "detect", "spikyshield", "kingsshield"}:
            roles.add("protect_positioning")
        if ability_id == "intimidate":
            roles.add("defensive_positioning")
        if move_ids & {"stealthrock", "spikes", "toxicspikes", "stickyweb"}:
            roles.add("entry_hazards")
        if move_ids & {"rapidspin", "defog", "mortalspin", "tidyup"}:
            roles.add("hazard_removal")
        if move_ids & {"uturn", "voltswitch", "flipturn", "partingshot", "chillyreception"}:
            roles.add("pivoting")
        if move_ids & {"recover", "roost", "slackoff", "synthesis", "morningsun", "softboiled", "wish"}:
            roles.add("recovery")
        if move_ids & {"swordsdance", "nastyplot", "dragondance", "calmmind", "bulkup", "quiverdance"}:
            roles.add("setup_cleaner")
        if any(self._move_power_hint(move) >= 90 for move in member.get("moves") or []):
            roles.add("immediate_damage")
        return {
            "slot": slot,
            "species": str(member.get("species") or member.get("name") or "Unknown"),
            "roles": sorted(roles),
        }

    def _to_id(self, value: Any) -> str:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())

    def _move_power_hint(self, move: Any) -> int:
        if not isinstance(move, dict):
            return 0
        try:
            return int(move.get("basePower") or move.get("power") or 0)
        except (TypeError, ValueError):
            return 0

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
