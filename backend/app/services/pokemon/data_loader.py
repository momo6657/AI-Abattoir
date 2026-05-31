"""
Pokemon Data Loader
Loads species, moves, abilities, items, and team templates from JSON files into database
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pokemon import (
    PokemonSpecies,
    PokemonMove,
    PokemonAbility,
    PokemonItem,
    PokemonTeam,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "pokemon"


class PokemonDataLoader:
    """Loads Pokemon data from JSON files into database"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load_all(self) -> Dict[str, int]:
        """Load all data files and return counts"""
        counts = {}
        counts["species"] = await self.load_species()
        counts["moves"] = await self.load_moves()
        counts["abilities"] = await self.load_abilities()
        counts["items"] = await self.load_items()
        logger.info(f"Loaded Pokemon data: {counts}")
        return counts

    async def load_species(self) -> int:
        """Load species data from species.json"""
        filepath = DATA_DIR / "species.json"
        if not filepath.exists():
            logger.warning(f"Species file not found: {filepath}")
            return 0

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for entry in data.get("species", []):
            stmt = select(PokemonSpecies).where(PokemonSpecies.id == entry["id"])
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                continue

            species = PokemonSpecies(
                id=entry["id"],
                name=entry["name"],
                name_zh=entry["name_zh"],
                form=entry.get("form"),
                types=entry["types"],
                base_stats=entry["base_stats"],
                abilities=entry["abilities"],
                hidden_ability=entry.get("hidden_ability"),
                weight=entry["weight"],
                gender_ratio=entry.get("gender_ratio", {}),
            )
            self.db.add(species)
            count += 1

        await self.db.commit()
        logger.info(f"Loaded {count} species")
        return count

    async def load_moves(self) -> int:
        """Load moves data from moves.json"""
        filepath = DATA_DIR / "moves.json"
        if not filepath.exists():
            logger.warning(f"Moves file not found: {filepath}")
            return 0

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for entry in data.get("moves", []):
            stmt = select(PokemonMove).where(PokemonMove.name == entry["name"])
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                continue

            move = PokemonMove(
                name=entry["name"],
                name_zh=entry["name_zh"],
                type=entry["type"],
                category=entry["category"],
                power=entry.get("power"),
                accuracy=entry.get("accuracy"),
                pp=entry.get("pp", 10),
                priority=entry.get("priority", 0),
                target=entry.get("target", "normal"),
                flags=entry.get("flags", {}),
                effect=entry.get("effect"),
                effect_data=entry.get("effect_data", {}),
            )
            self.db.add(move)
            count += 1

        await self.db.commit()
        logger.info(f"Loaded {count} moves")
        return count

    async def load_abilities(self) -> int:
        """Load abilities data from abilities.json"""
        filepath = DATA_DIR / "abilities.json"
        if not filepath.exists():
            logger.warning(f"Abilities file not found: {filepath}")
            return 0

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for entry in data.get("abilities", []):
            stmt = select(PokemonAbility).where(PokemonAbility.name == entry["name"])
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                continue

            ability = PokemonAbility(
                name=entry["name"],
                name_zh=entry["name_zh"],
                description=entry.get("description"),
                effect_data=entry.get("effect_data", {}),
            )
            self.db.add(ability)
            count += 1

        await self.db.commit()
        logger.info(f"Loaded {count} abilities")
        return count

    async def load_items(self) -> int:
        """Load items data from items.json"""
        filepath = DATA_DIR / "items.json"
        if not filepath.exists():
            logger.warning(f"Items file not found: {filepath}")
            return 0

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for entry in data.get("items", []):
            stmt = select(PokemonItem).where(PokemonItem.name == entry["name"])
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                continue

            item = PokemonItem(
                name=entry["name"],
                name_zh=entry["name_zh"],
                effect=entry.get("effect"),
                effect_data=entry.get("effect_data", {}),
            )
            self.db.add(item)
            count += 1

        await self.db.commit()
        logger.info(f"Loaded {count} items")
        return count

    async def create_team_from_template(
        self,
        template_id: str,
        agent_id: str,
    ) -> Optional[PokemonTeam]:
        """Create a PokemonTeam from a template"""
        filepath = DATA_DIR / "team_templates.json"
        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for template in data.get("team_templates", []):
            if template["id"] == template_id:
                team = PokemonTeam(
                    agent_id=agent_id,
                    name=template["name"],
                    format=template.get("format", "vgc2024"),
                    pokemon_list=template["pokemon"],
                    source="template",
                )
                self.db.add(team)
                await self.db.commit()
                await self.db.refresh(team)
                return team

        return None
