"""
AI Decision Engine for Pokemon battles
Uses LLM to make strategic decisions based on battle state
"""

import json
import logging
from typing import Dict, List, Any, Optional
from app.services.pokemon.battle_state import BattleState, PokemonState
from app.services.pokemon.type_chart import TypeChart
from app.services.pokemon.damage_calculator import DamageCalculator

logger = logging.getLogger(__name__)


class AIDecisionEngine:
    """AI decision engine for Pokemon battles"""

    def __init__(self):
        self.type_chart = TypeChart()
        self.damage_calculator = DamageCalculator()

    async def make_decision(
        self,
        battle_state: BattleState,
        player_num: int,
        llm_client: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Make decisions for all active Pokemon of a player

        Args:
            battle_state: Current battle state
            player_num: 1 or 2
            llm_client: Optional LLM client for advanced decisions

        Returns:
            List of actions, one per active Pokemon
        """
        player = battle_state.player1 if player_num == 1 else battle_state.player2
        opponent = battle_state.player2 if player_num == 1 else battle_state.player1

        actions = []

        for idx in player.active:
            pokemon = player.team[idx]
            if pokemon.is_fainted:
                continue

            # Try LLM-based decision if available
            if llm_client:
                try:
                    action = await self._llm_decision(
                        llm_client, pokemon, player, opponent, battle_state
                    )
                    if action:
                        actions.append(action)
                        continue
                except Exception as e:
                    logger.warning(f"LLM decision failed: {e}")

            # Fallback to rule-based decision
            action = self._rule_based_decision(pokemon, player, opponent, battle_state)
            actions.append(action)

        return actions

    async def _llm_decision(
        self,
        llm_client: Any,
        pokemon: PokemonState,
        player: Any,
        opponent: Any,
        battle_state: BattleState,
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to make a strategic decision"""
        prompt = self._build_llm_prompt(pokemon, player, opponent, battle_state)

        response = await llm_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a Pokemon VGC doubles battle expert. Respond with JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500,
        )

        content = response.choices[0].message.content
        try:
            decision = json.loads(content)
            return self._parse_llm_decision(decision, pokemon, player, opponent)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse LLM decision: {e}")
            return None

    def _build_llm_prompt(
        self,
        pokemon: PokemonState,
        player: Any,
        opponent: Any,
        battle_state: BattleState,
    ) -> str:
        """Build prompt for LLM decision making"""
        opponent_active = []
        for idx in opponent.active:
            opp = opponent.team[idx]
            if not opp.is_fainted:
                opponent_active.append({
                    "name": opp.name,
                    "types": opp.types,
                    "hp_percent": f"{opp.hp_percent():.0%}",
                    "status": opp.status,
                })

        ally_active = []
        for idx in player.active:
            ally = player.team[idx]
            if idx != pokemon.position and not ally.is_fainted:
                ally_active.append({
                    "name": ally.name,
                    "types": ally.types,
                    "hp_percent": f"{ally.hp_percent():.0%}",
                })

        moves_info = []
        for i, move in enumerate(pokemon.moves):
            moves_info.append({
                "index": i,
                "name": move.get("name", "Unknown"),
                "type": move.get("type", "Normal"),
                "power": move.get("power", 0),
                "accuracy": move.get("accuracy", 100),
                "category": move.get("category", "physical"),
            })

        prompt = f"""You are controlling {pokemon.name} in a VGC double battle.

Your Pokemon: {pokemon.name}
- Types: {pokemon.types}
- HP: {pokemon.hp_percent():.0%} ({pokemon.current_hp}/{pokemon.max_hp})
- Status: {pokemon.status or 'None'}
- Moves: {json.dumps(moves_info, indent=2)}

Opposing Pokemon:
{json.dumps(opponent_active, indent=2)}

Ally Pokemon:
{json.dumps(ally_active, indent=2)}

Battle Context:
- Turn: {battle_state.turn}
- Weather: {battle_state.weather.value}
- Trick Room: {battle_state.trick_room}

Choose the best move and target. Respond with JSON:
{{"action": "move", "move_index": <int>, "target": [<player_num>, <pokemon_index>], "reasoning": "<brief explanation>"}}

Target format: [player_num, pokemon_index] where player_num is 1 or 2, pokemon_index is the position."""

        return prompt

    def _parse_llm_decision(
        self,
        decision: Dict,
        pokemon: PokemonState,
        player: Any,
        opponent: Any,
    ) -> Optional[Dict[str, Any]]:
        """Parse LLM decision into action format"""
        action_type = decision.get("action", "move")

        if action_type == "move":
            move_index = decision.get("move_index", 0)
            target = decision.get("target", [2 if player == player else 1, 0])

            return {
                "pokemon_index": pokemon.position,
                "action_type": "move",
                "move_index": move_index,
                "target": tuple(target),
            }
        elif action_type == "switch":
            switch_to = decision.get("switch_to", 0)
            return {
                "pokemon_index": pokemon.position,
                "action_type": "switch",
                "switch_to": switch_to,
            }

        return None

    def _rule_based_decision(
        self,
        pokemon: PokemonState,
        player: Any,
        opponent: Any,
        battle_state: BattleState,
    ) -> Dict[str, Any]:
        """Rule-based fallback decision making"""
        # Get active opponent Pokemon
        opponent_active = []
        for idx in opponent.active:
            opp = opponent.team[idx]
            if not opp.is_fainted:
                opponent_active.append((idx, opp))

        if not opponent_active:
            return {
                "pokemon_index": pokemon.position,
                "action_type": "move",
                "move_index": 0,
                "target": (2, 0),
            }

        # Find best move and target
        best_move_idx = 0
        best_target = (2, opponent_active[0][0])
        best_score = -999

        for move_idx, move in enumerate(pokemon.moves):
            if move.get("category") == "status":
                continue

            move_type = move.get("type", "Normal")
            move_power = move.get("power", 0)

            for opp_idx, opp_pokemon in opponent_active:
                # Calculate type effectiveness
                effectiveness = self.type_chart.get_dual_type_effectiveness(move_type, opp_pokemon.types)

                # STAB bonus
                stab = 1.5 if move_type in pokemon.types else 1.0

                # Score = base power * effectiveness * STAB
                score = move_power * effectiveness * stab

                # Bonus for KO potential
                if effectiveness >= 2.0:
                    score *= 1.2

                if score > best_score:
                    best_score = score
                    best_move_idx = move_idx
                    best_target = (2, opp_idx)

        # Check if should switch (low HP)
        if pokemon.hp_percent() < 0.25:
            bench = player.get_bench_pokemon()
            if bench:
                # Find best bench Pokemon
                best_bench = max(bench, key=lambda p: p.current_hp)
                return {
                    "pokemon_index": pokemon.position,
                    "action_type": "switch",
                    "switch_to": best_bench.position,
                }

        return {
            "pokemon_index": pokemon.position,
            "action_type": "move",
            "move_index": best_move_idx,
            "target": best_target,
        }
