"""
Battle Engine - Core battle logic for Pokemon VGC double battles
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
from app.services.pokemon.battle_state import (
    BattleState, BattlePhase, PokemonState, PlayerState, Weather
)
from app.services.pokemon.damage_calculator import DamageCalculator
from app.services.pokemon.type_chart import TypeChart


class BattleAction:
    """Represents a player's action for a turn"""
    def __init__(self, action_type: str, **kwargs):
        self.action_type = action_type  # "move", "switch", "tera"
        self.pokemon_index = kwargs.get("pokemon_index", 0)
        self.move_index = kwargs.get("move_index", 0)
        self.target = kwargs.get("target")  # (player_num, pokemon_index)
        self.switch_to = kwargs.get("switch_to")  # pokemon index
        self.use_tera = kwargs.get("use_tera", False)


class BattleEngine:
    """Core battle engine for VGC double battles"""
    _move_catalog: Dict[str, Dict[str, Any]] | None = None

    def __init__(self):
        self.damage_calculator = DamageCalculator()
        self.type_chart = TypeChart()

    def create_battle(self, battle_id: str, p1_team: List[Dict], p2_team: List[Dict],
                     p1_agent_id: str, p2_agent_id: str) -> BattleState:
        """Initialize a new battle from team data"""
        p1_state = PlayerState(agent_id=p1_agent_id)
        p2_state = PlayerState(agent_id=p2_agent_id)

        for i, pokemon_data in enumerate(p1_team):
            p1_state.team.append(self._create_pokemon_state(pokemon_data, i))
        for i, pokemon_data in enumerate(p2_team):
            p2_state.team.append(self._create_pokemon_state(pokemon_data, i))

        # Select first 2 Pokemon for double battle
        p1_state.active = [0, 1] if len(p1_state.team) >= 2 else [0]
        p2_state.active = [0, 1] if len(p2_state.team) >= 2 else [0]

        for idx in p1_state.active:
            p1_state.team[idx].is_active = True
        for idx in p2_state.active:
            p2_state.team[idx].is_active = True

        return BattleState(
            battle_id=battle_id,
            player1=p1_state,
            player2=p2_state,
            phase=BattlePhase.BATTLE,
        )

    def from_dict(self, data: Dict[str, Any]) -> BattleState:
        """Rehydrate battle state from API/database JSON."""
        state = BattleState.from_dict(data)
        for player in (state.player1, state.player2):
            for pokemon in player.team:
                pokemon.moves = [self._normalize_move(move) for move in pokemon.moves]
        return state

    def _create_pokemon_state(self, data: Dict, position: int) -> PokemonState:
        """Create PokemonState from team data"""
        base_stats = data.get("stats", {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100})

        # Calculate HP from base stats (simplified)
        hp_stat = base_stats.get("hp", 100)
        level = data.get("level", 50)
        max_hp = int((2 * hp_stat * level / 100) + level + 10)

        # Calculate other stats (simplified)
        def calc_stat(base: int) -> int:
            return int((2 * base * level / 100) + 5)

        stats = {
            "hp": max_hp,
            "atk": calc_stat(base_stats.get("atk", 100)),
            "def": calc_stat(base_stats.get("def", 100)),
            "spa": calc_stat(base_stats.get("spa", 100)),
            "spd": calc_stat(base_stats.get("spd", 100)),
            "spe": calc_stat(base_stats.get("spe", 100)),
        }

        return PokemonState(
            species=data.get("species", "Unknown"),
            name=data.get("name", data.get("species", "Unknown")),
            level=level,
            types=data.get("types", ["Normal"]),
            stats=stats,
            current_hp=max_hp,
            max_hp=max_hp,
            moves=[self._normalize_move(move) for move in data.get("moves", [])],
            ability=data.get("ability", ""),
            item=data.get("item", ""),
            position=position,
        )

    @classmethod
    def _load_move_catalog(cls) -> Dict[str, Dict[str, Any]]:
        if cls._move_catalog is not None:
            return cls._move_catalog

        cls._move_catalog = {}
        data_path = Path(__file__).resolve().parents[3] / "data" / "pokemon" / "moves.json"
        if data_path.exists():
            with open(data_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            for move in payload.get("moves", []):
                if isinstance(move, dict) and move.get("name"):
                    cls._move_catalog[move["name"].lower()] = move
        return cls._move_catalog

    def _normalize_move(self, move: Any) -> Dict[str, Any]:
        if isinstance(move, dict):
            return move
        if isinstance(move, str):
            catalog_move = self._load_move_catalog().get(move.lower())
            if catalog_move:
                return dict(catalog_move)
            return {
                "name": move,
                "type": "Normal",
                "category": "physical",
                "power": 50,
                "accuracy": 100,
                "pp": 10,
                "priority": 0,
                "target": "normal",
            }
        return {
            "name": "Struggle",
            "type": "Normal",
            "category": "physical",
            "power": 50,
            "accuracy": 100,
            "pp": 1,
            "priority": 0,
            "target": "normal",
        }

    def get_valid_actions(self, state: BattleState, player_num: int) -> List[BattleAction]:
        """Get all valid actions for a player"""
        player = state.player1 if player_num == 1 else state.player2
        actions = []

        for idx in player.active:
            pokemon = player.team[idx]
            if pokemon.is_fainted:
                continue

            # Move actions
            for move_idx, move in enumerate(pokemon.moves):
                move = self._normalize_move(move)
                pokemon.moves[move_idx] = move
                targets = self._get_valid_targets(state, player_num, move)
                for target in targets:
                    actions.append(BattleAction(
                        "move",
                        pokemon_index=idx,
                        move_index=move_idx,
                        target=target,
                    ))

            # Switch actions
            for bench_idx, bench_pokemon in enumerate(player.team):
                if bench_idx not in player.active and not bench_pokemon.is_fainted:
                    actions.append(BattleAction(
                        "switch",
                        pokemon_index=idx,
                        switch_to=bench_idx,
                    ))

        return actions

    def _get_valid_targets(self, state: BattleState, player_num: int, move: Dict) -> List[tuple]:
        """Get valid targets for a move"""
        targets = []
        opponent = state.player2 if player_num == 1 else state.player1
        player = state.player1 if player_num == 1 else state.player2

        target_type = move.get("target", "normal")

        if target_type == "normal":
            # Can target any active Pokemon
            for idx in opponent.active:
                if not opponent.team[idx].is_fainted:
                    targets.append((2 if player_num == 1 else 1, idx))
            for idx in player.active:
                if not player.team[idx].is_fainted:
                    targets.append((player_num, idx))
        elif target_type == "allAdjacentFoes":
            # Targets all opposing Pokemon (no target selection needed)
            targets.append(("opponent", "all"))
        elif target_type == "self":
            targets.append((player_num, "self"))
        elif target_type == "allySide":
            targets.append((player_num, "side"))

        return targets if targets else [(2 if player_num == 1 else 1, 0)]

    def execute_turn(self, state: BattleState, p1_actions: List[Any],
                    p2_actions: List[Any]) -> BattleState:
        """Execute one turn of battle"""
        if state.is_over():
            return state

        state.turn += 1
        state.add_log("turn_start", {"turn": state.turn})

        # Collect all actions with speed
        all_actions = []
        p1_actions = [self._coerce_action(action) for action in p1_actions]
        p2_actions = [self._coerce_action(action) for action in p2_actions]

        for action in p1_actions:
            pokemon = state.player1.team[action.pokemon_index]
            speed = self._get_effective_speed(pokemon, state)
            all_actions.append((action, 1, speed))

        for action in p2_actions:
            pokemon = state.player2.team[action.pokemon_index]
            speed = self._get_effective_speed(pokemon, state)
            all_actions.append((action, 2, speed))

        # Sort by priority then speed (descending)
        # Trick Room reverses speed order
        all_actions.sort(
            key=lambda x: (
                self._get_action_priority(x[0], state, x[1]),
                x[2] if not state.trick_room else -x[2]
            ),
            reverse=True
        )

        # Execute actions
        for action, player_num, _ in all_actions:
            if state.is_over():
                break

            pokemon = (state.player1 if player_num == 1 else state.player2).team[action.pokemon_index]
            if pokemon.is_fainted:
                continue

            if action.action_type == "move":
                self._execute_move(state, action, player_num)
            elif action.action_type == "switch":
                self._execute_switch(state, action, player_num)

        # End of turn effects
        self._process_end_of_turn(state)

        # Check for winner
        state.check_winner()

        state.add_log("turn_end", {"turn": state.turn})
        return state

    def _coerce_action(self, action: Any) -> BattleAction:
        if isinstance(action, BattleAction):
            return action
        if isinstance(action, dict):
            action = dict(action)
            action_type = action.pop("action_type", action.pop("type", "move"))
            target = action.get("target")
            if isinstance(target, list):
                action["target"] = tuple(target)
            return BattleAction(action_type, **action)
        raise TypeError(f"Unsupported battle action: {type(action)!r}")

    def _get_action_priority(self, action: BattleAction, state: BattleState, player_num: int = 1) -> int:
        """Get priority of an action"""
        if action.action_type == "switch":
            return 100  # Switches happen first

        player = state.player1 if player_num == 1 else state.player2
        pokemon = player.team[action.pokemon_index]

        if action.move_index < len(pokemon.moves):
            move = self._normalize_move(pokemon.moves[action.move_index])
            pokemon.moves[action.move_index] = move
            return move.get("priority", 0)
        return 0

    def _get_effective_speed(self, pokemon: PokemonState, state: BattleState) -> int:
        """Calculate effective speed with modifiers"""
        base_speed = pokemon.stats.get("spe", 100)

        # Stat stage modifier
        speed_stage = pokemon.stat_stages.get("spe", 0)
        if speed_stage >= 0:
            speed_mult = (2 + speed_stage) / 2
        else:
            speed_mult = 2 / (2 - speed_stage)

        speed = int(base_speed * speed_mult)

        # Paralysis halves speed
        if pokemon.status == "paralysis":
            speed //= 2

        # Choice Scarf
        if pokemon.item == "Choice Scarf":
            speed = int(speed * 1.5)

        return speed

    def _execute_move(self, state: BattleState, action: BattleAction, player_num: int):
        """Execute a move action"""
        attacker = (state.player1 if player_num == 1 else state.player2).team[action.pokemon_index]

        if attacker.is_fainted or not attacker.can_move():
            return

        if action.move_index >= len(attacker.moves):
            return

        move = self._normalize_move(attacker.moves[action.move_index])
        attacker.moves[action.move_index] = move

        # Status moves
        if move.get("category") == "status":
            state.add_log("move", {
                "pokemon": attacker.name,
                "move": move.get("name", "Unknown"),
                "type": "status"
            })
            return

        # Get target
        if action.target:
            target_player_num, target_idx = action.target
            if isinstance(target_idx, int):
                defender = (state.player1 if target_player_num == 1 else state.player2).team[target_idx]
            else:
                defender = None
        else:
            # Default target: first active opponent
            opponent = state.player2 if player_num == 1 else state.player1
            defender = opponent.team[opponent.active[0]] if opponent.active else None

        if not defender or defender.is_fainted:
            return

        # Calculate type effectiveness
        move_type = move.get("type", "Normal")
        type_effectiveness = self.type_chart.get_dual_type_effectiveness(move_type, defender.types)

        # STAB check
        stab = move_type in attacker.types

        # Critical hit check
        critical = self.damage_calculator.check_critical()

        # Calculate damage
        damage = self.damage_calculator.calculate_damage(
            attacker={
                "level": attacker.level,
                "atk": attacker.stats.get("atk", 100),
                "spa": attacker.stats.get("spa", 100),
            },
            defender={
                "def": defender.stats.get("def", 100),
                "spd": defender.stats.get("spd", 100),
            },
            move=move,
            type_effectiveness=type_effectiveness,
            stab=stab,
            critical=critical,
        )

        # Apply damage
        defender.current_hp = max(0, defender.current_hp - damage)

        state.add_log("move", {
            "attacker": attacker.name,
            "defender": defender.name,
            "move": move.get("name", "Unknown"),
            "damage": damage,
            "effectiveness": type_effectiveness,
            "critical": critical,
            "defender_hp": defender.current_hp,
        })

        # Check faint
        if defender.current_hp <= 0:
            defender.is_fainted = True
            defender.is_active = False
            state.add_log("faint", {"pokemon": defender.name})

    def _execute_switch(self, state: BattleState, action: BattleAction, player_num: int):
        """Execute a switch action"""
        player = state.player1 if player_num == 1 else state.player2

        # Deactivate current Pokemon
        player.team[action.pokemon_index].is_active = False

        # Activate new Pokemon
        new_pokemon = player.team[action.switch_to]
        new_pokemon.is_active = True

        # Update active list
        player.active = [
            action.switch_to if i == action.pokemon_index else i
            for i in player.active
        ]

        state.add_log("switch", {
            "player": player_num,
            "from": player.team[action.pokemon_index].name,
            "to": new_pokemon.name,
        })

    def _process_end_of_turn(self, state: BattleState):
        """Process end of turn effects (weather, status, items)"""
        # Weather damage
        if state.weather != Weather.NONE:
            for player in [state.player1, state.player2]:
                for idx in player.active:
                    pokemon = player.team[idx]
                    if pokemon.is_fainted:
                        continue

                    if state.weather == Weather.SAND:
                        if not any(t in ["Rock", "Ground", "Steel"] for t in pokemon.types):
                            damage = max(1, pokemon.max_hp // 16)
                            pokemon.current_hp = max(0, pokemon.current_hp - damage)
                            if pokemon.current_hp <= 0:
                                pokemon.is_fainted = True

                    elif state.weather == Weather.HAIL:
                        if "Ice" not in pokemon.types:
                            damage = max(1, pokemon.max_hp // 16)
                            pokemon.current_hp = max(0, pokemon.current_hp - damage)
                            if pokemon.current_hp <= 0:
                                pokemon.is_fainted = True

        # Weather duration
        if state.weather_turns > 0:
            state.weather_turns -= 1
            if state.weather_turns == 0:
                state.weather = Weather.NONE

        # Trick Room duration
        if state.trick_room_turns > 0:
            state.trick_room_turns -= 1
            if state.trick_room_turns == 0:
                state.trick_room = False

        # Status damage
        for player in [state.player1, state.player2]:
            for idx in player.active:
                pokemon = player.team[idx]
                if pokemon.is_fainted:
                    continue

                if pokemon.status == "poison":
                    damage = max(1, pokemon.max_hp // 8)
                    pokemon.current_hp = max(0, pokemon.current_hp - damage)
                elif pokemon.status == "burn":
                    damage = max(1, pokemon.max_hp // 16)
                    pokemon.current_hp = max(0, pokemon.current_hp - damage)

                if pokemon.current_hp <= 0:
                    pokemon.is_fainted = True
                    pokemon.is_active = False
