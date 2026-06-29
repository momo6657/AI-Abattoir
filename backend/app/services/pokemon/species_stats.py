"""Pokemon species usage and performance statistics.

Tracks which Pokemon species are used most often, their win rates,
and common movesets/items based on battle data.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import PokemonBattle, PokemonTeam, PokemonSpecies
from app.services.pokemon.battle_outcome import did_team_win, winner_team_id


class PokemonSpeciesStats:
    """Tracks Pokemon species usage and performance."""

    async def get_species_usage(
        self,
        db: AsyncSession,
        battle_format: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get most used Pokemon species with win rates."""
        # Get all teams
        query = select(PokemonTeam)
        if battle_format:
            query = query.where(PokemonTeam.format == battle_format)
        result = await db.execute(query)
        teams = result.scalars().all()

        # Count usage per species
        species_usage: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "usage_count": 0,
            "wins": 0,
            "losses": 0,
            "teams": set(),
        })

        for team in teams:
            pokemon_list = team.pokemon_list or []
            for pokemon in pokemon_list:
                species = pokemon.get("species") or pokemon.get("name", "Unknown")
                species_usage[species]["usage_count"] += 1
                species_usage[species]["teams"].add(str(team.id))

        # Get battle results to calculate win rates
        battle_query = select(PokemonBattle)
        if battle_format:
            battle_query = battle_query.where(PokemonBattle.battle_format == battle_format)
        battle_result = await db.execute(battle_query)
        battles = battle_result.scalars().all()

        for battle in battles:
            if not battle.winner:
                continue

            # Get winning team
            resolved_winner_team_id = winner_team_id(battle)
            if not resolved_winner_team_id:
                continue
            loser_team_id = (
                battle.player2_team_id
                if resolved_winner_team_id == battle.player1_team_id
                else battle.player1_team_id
            )

            # Count wins
            if resolved_winner_team_id:
                winner_team = await db.get(PokemonTeam, resolved_winner_team_id)
                if winner_team:
                    for pokemon in (winner_team.pokemon_list or []):
                        species = pokemon.get("species") or pokemon.get("name", "Unknown")
                        if species in species_usage:
                            species_usage[species]["wins"] += 1

            # Count losses
            if loser_team_id:
                loser_team = await db.get(PokemonTeam, loser_team_id)
                if loser_team:
                    for pokemon in (loser_team.pokemon_list or []):
                        species = pokemon.get("species") or pokemon.get("name", "Unknown")
                        if species in species_usage:
                            species_usage[species]["losses"] += 1

        # Build result
        result = []
        for species, data in sorted(
            species_usage.items(),
            key=lambda x: x[1]["usage_count"],
            reverse=True,
        )[:limit]:
            total = data["wins"] + data["losses"]
            result.append({
                "species": species,
                "usage_count": data["usage_count"],
                "wins": data["wins"],
                "losses": data["losses"],
                "win_rate": round(data["wins"] / total * 100, 1) if total else 0,
                "team_count": len(data["teams"]),
            })

        return result

    async def get_species_performance(
        self,
        db: AsyncSession,
        species_name: str,
    ) -> dict[str, Any]:
        """Get detailed performance stats for a specific species."""
        # Find all teams containing this species
        result = await db.execute(select(PokemonTeam))
        teams = result.scalars().all()

        teams_with_species = []
        for team in teams:
            for pokemon in (team.pokemon_list or []):
                name = pokemon.get("species") or pokemon.get("name", "")
                if name.lower() == species_name.lower():
                    teams_with_species.append({
                        "team_id": str(team.id),
                        "team_format": team.format,
                        "pokemon_data": pokemon,
                    })
                    break

        # Calculate win rate from battles
        wins = 0
        losses = 0
        for team_data in teams_with_species:
            team_id = uuid.UUID(team_data["team_id"])

            # Find battles where this team participated
            battle_result = await db.execute(
                select(PokemonBattle).where(
                    (PokemonBattle.player1_team_id == team_id)
                    | (PokemonBattle.player2_team_id == team_id)
                )
            )
            battles = battle_result.scalars().all()

            for battle in battles:
                if not battle.winner:
                    continue
                if did_team_win(battle, team_id):
                    wins += 1
                else:
                    losses += 1

        # Get species info from database
        species_result = await db.execute(
            select(PokemonSpecies).where(
                func.lower(PokemonSpecies.name) == species_name.lower()
            )
        )
        species = species_result.scalar_one_or_none()

        total = wins + losses
        return {
            "species": species_name,
            "species_info": {
                "id": species.id if species else None,
                "name_zh": species.name_zh if species else None,
                "types": species.types if species else [],
                "base_stats": species.base_stats if species else {},
            } if species else None,
            "team_count": len(teams_with_species),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / total * 100, 1) if total else 0,
            "teams": teams_with_species[:10],  # Limit to 10 teams
        }


pokemon_species_stats = PokemonSpeciesStats()
