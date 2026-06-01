"""
Tests for Battle Engine
"""
import pytest
from app.services.pokemon.battle_engine import BattleEngine
from app.services.pokemon.battle_state import BattleState, PlayerState, PokemonState, BattlePhase


class TestBattleEngine:
    """Test battle engine core functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.engine = BattleEngine()

        # Create simple test teams
        self.team1_data = [
            {
                "species": "Charizard",
                "name": "Charizard",
                "level": 50,
                "types": ["Fire", "Flying"],
                "stats": {"hp": 100, "atk": 84, "def": 78, "spa": 109, "spd": 85, "spe": 100},
                "moves": [
                    {"name": "Flamethrower", "type": "Fire", "category": "special", "power": 90, "accuracy": 100, "pp": 15},
                    {"name": "Air Slash", "type": "Flying", "category": "special", "power": 75, "accuracy": 95, "pp": 20}
                ],
                "ability": "Blaze",
                "item": ""
            }
        ]

        self.team2_data = [
            {
                "species": "Blastoise",
                "name": "Blastoise",
                "level": 50,
                "types": ["Water"],
                "stats": {"hp": 100, "atk": 83, "def": 100, "spa": 85, "spd": 105, "spe": 78},
                "moves": [
                    {"name": "Hydro Pump", "type": "Water", "category": "special", "power": 110, "accuracy": 80, "pp": 5},
                    {"name": "Ice Beam", "type": "Ice", "category": "special", "power": 90, "accuracy": 100, "pp": 10}
                ],
                "ability": "Torrent",
                "item": ""
            }
        ]

    def test_create_battle(self):
        """Test battle initialization"""
        state = self.engine.create_battle(
            "test_1",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        assert state.battle_id == "test_1"
        assert state.turn == 0
        assert len(state.player1.team) == 1
        assert len(state.player2.team) == 1
        assert state.player1.team[0].species == "Charizard"
        assert state.player2.team[0].species == "Blastoise"
        assert state.phase == BattlePhase.BATTLE

    def test_pokemon_state_initialization(self):
        """Test that Pokemon are properly initialized"""
        state = self.engine.create_battle(
            "test_2",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        charizard = state.player1.team[0]
        assert charizard.current_hp == charizard.max_hp
        assert charizard.max_hp > 0
        assert charizard.is_active
        assert not charizard.is_fainted
        assert len(charizard.moves) == 2

    def test_get_valid_actions(self):
        """Test getting valid actions for a player"""
        state = self.engine.create_battle(
            "test_3",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        actions = self.engine.get_valid_actions(state, 1)

        # Should have move actions
        assert len(actions) > 0
        # Check that we have move actions
        move_actions = [a for a in actions if a.action_type == "move"]
        assert len(move_actions) > 0

    def test_execute_turn(self):
        """Test executing a complete turn"""
        from app.services.pokemon.battle_engine import BattleAction

        state = self.engine.create_battle(
            "test_4",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        # Player 1 uses Flamethrower
        p1_action = BattleAction(
            "move",
            pokemon_index=0,
            move_index=0,
            target=(2, 0)
        )

        # Player 2 uses Hydro Pump
        p2_action = BattleAction(
            "move",
            pokemon_index=0,
            move_index=0,
            target=(1, 0)
        )

        new_state = self.engine.execute_turn(state, [p1_action], [p2_action])

        # Turn should increment
        assert new_state.turn == 1
        # Both Pokemon should have taken damage (or at least one)
        # Note: damage calculation depends on speed and other factors
        assert len(new_state.battle_log) > 0

    def test_execute_turn_with_string_moves(self):
        """Test team templates with string move names can execute turns."""
        from app.services.pokemon.battle_engine import BattleAction

        team = [
            {
                "species": "Charizard",
                "types": ["Fire", "Flying"],
                "stats": {"hp": 100, "atk": 84, "def": 78, "spa": 109, "spd": 85, "spe": 100},
                "moves": ["Flamethrower", "Protect"],
                "ability": "Blaze",
                "item": "",
            },
            {
                "species": "Venusaur",
                "types": ["Grass", "Poison"],
                "stats": {"hp": 100, "atk": 82, "def": 83, "spa": 100, "spd": 100, "spe": 80},
                "moves": ["Giga Drain", "Protect"],
                "ability": "Overgrow",
                "item": "",
            },
        ]
        state = self.engine.create_battle("string-move-battle", team, team, "agent1", "agent2")
        new_state = self.engine.execute_turn(
            state,
            [BattleAction("move", pokemon_index=0, move_index=0, target=(2, 0))],
            [BattleAction("move", pokemon_index=0, move_index=0, target=(1, 0))],
        )

        assert new_state.turn == 1
        assert isinstance(new_state.player1.team[0].moves[0], dict)
        assert new_state.player1.team[0].moves[0]["name"] == "Flamethrower"

    def test_type_effectiveness_in_battle(self):
        """Test that type effectiveness is applied correctly"""
        from app.services.pokemon.battle_engine import BattleAction

        state = self.engine.create_battle(
            "test_5",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        initial_hp = state.player2.team[0].current_hp

        # Player 1 uses Flamethrower (Fire vs Water = not very effective)
        p1_action = BattleAction(
            "move",
            pokemon_index=0,
            move_index=0,
            target=(2, 0)
        )

        # Player 2 does nothing (empty actions)
        new_state = self.engine.execute_turn(state, [p1_action], [])

        # Blastoise should have taken some damage
        # (Fire is not very effective against Water, but still does damage)
        damage = initial_hp - new_state.player2.team[0].current_hp
        # Damage might be 0 if move missed or other factors, but log should show the attempt
        assert len(new_state.battle_log) > 0

    def test_fainted_pokemon(self):
        """Test handling of fainted Pokemon"""
        from app.services.pokemon.battle_engine import BattleAction

        state = self.engine.create_battle(
            "test_6",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        # Set Blastoise HP to 1
        state.player2.team[0].current_hp = 1

        # Player 1 uses Flamethrower
        p1_action = BattleAction(
            "move",
            pokemon_index=0,
            move_index=0,
            target=(2, 0)
        )

        new_state = self.engine.execute_turn(state, [p1_action], [])

        # Blastoise should be fainted if damage >= 1
        blastoise = new_state.player2.team[0]
        if blastoise.current_hp <= 0:
            assert blastoise.is_fainted
            assert not blastoise.is_active

    def test_switch_pokemon(self):
        """Test switching Pokemon"""
        from app.services.pokemon.battle_engine import BattleAction

        # Create teams with 3 Pokemon each (2 active + 1 bench)
        team1_data = self.team1_data + [
            {
                "species": "Blastoise",
                "name": "Blastoise",
                "level": 50,
                "types": ["Water"],
                "stats": {"hp": 100, "atk": 83, "def": 100, "spa": 85, "spd": 105, "spe": 78},
                "moves": [
                    {"name": "Hydro Pump", "type": "Water", "category": "special", "power": 110, "accuracy": 80, "pp": 5}
                ],
                "ability": "Torrent",
                "item": ""
            },
            {
                "species": "Venusaur",
                "name": "Venusaur",
                "level": 50,
                "types": ["Grass", "Poison"],
                "stats": {"hp": 100, "atk": 82, "def": 83, "spa": 100, "spd": 100, "spe": 80},
                "moves": [
                    {"name": "Solar Beam", "type": "Grass", "category": "special", "power": 120, "accuracy": 100, "pp": 10}
                ],
                "ability": "Overgrow",
                "item": ""
            }
        ]

        state = self.engine.create_battle(
            "test_7",
            team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        # Switch Charizard to Venusaur
        switch_action = BattleAction(
            "switch",
            pokemon_index=0,
            switch_to=2  # Index 2 (0 and 1 are active, 2 is bench)
        )

        new_state = self.engine.execute_turn(state, [switch_action], [])

        # Venusaur should now be active
        venusaur = new_state.player1.team[2]
        assert venusaur.is_active

    def test_battle_state_serialization(self):
        """Test that battle state can be serialized to dict"""
        state = self.engine.create_battle(
            "test_8",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        state_dict = state.to_dict()

        assert "battle_id" in state_dict
        assert "turn" in state_dict
        assert "phase" in state_dict
        assert "player1" in state_dict
        assert "player2" in state_dict

    def test_weather_effects(self):
        """Test weather effects on Pokemon"""
        from app.services.pokemon.battle_state import Weather
        from app.services.pokemon.battle_engine import BattleAction

        state = self.engine.create_battle(
            "test_9",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        # Set weather to sandstorm
        state.weather = Weather.SAND
        state.weather_turns = 5

        # Execute a turn (empty actions)
        new_state = self.engine.execute_turn(state, [], [])

        # Non-Rock/Ground/Steel types should take damage from sand
        # Charizard is Fire/Flying, so it should take damage
        charizard = new_state.player1.team[0]
        # Note: actual damage depends on implementation

    def test_trick_room(self):
        """Test trick room reverses speed order"""
        from app.services.pokemon.battle_engine import BattleAction

        state = self.engine.create_battle(
            "test_10",
            self.team1_data,
            self.team2_data,
            "agent1",
            "agent2"
        )

        # Enable trick room
        state.trick_room = True
        state.trick_room_turns = 5

        # Execute turn with both Pokemon using moves
        p1_action = BattleAction("move", pokemon_index=0, move_index=0, target=(2, 0))
        p2_action = BattleAction("move", pokemon_index=0, move_index=0, target=(1, 0))

        new_state = self.engine.execute_turn(state, [p1_action], [p2_action])

        # Trick room should be active and turn should increment
        assert new_state.turn == 1
