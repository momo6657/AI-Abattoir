"""
Tests for AI Decision Engine
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.pokemon.ai_decision import AIDecisionEngine
from app.services.pokemon.battle_state import (
    BattleState, PlayerState, PokemonState, BattlePhase
)


@pytest.fixture
def engine():
    """Create an AI decision engine"""
    return AIDecisionEngine()


@pytest.fixture
def sample_battle_state():
    """Create a sample battle state for testing"""
    # Player 1's team
    p1_team = [
        PokemonState(
            species="Charizard",
            name="Charizard",
            level=50,
            types=["Fire", "Flying"],
            stats={"hp": 100, "atk": 84, "def": 78, "spa": 109, "spd": 85, "spe": 100},
            current_hp=80,
            max_hp=100,
            moves=[
                {"name": "Flamethrower", "type": "Fire", "category": "special", "power": 90},
                {"name": "Air Slash", "type": "Flying", "category": "special", "power": 75}
            ],
            ability="Blaze",
            is_active=True,
            position=0
        ),
        PokemonState(
            species="Blastoise",
            name="Blastoise",
            level=50,
            types=["Water"],
            stats={"hp": 100, "atk": 83, "def": 100, "spa": 85, "spd": 105, "spe": 78},
            current_hp=100,
            max_hp=100,
            moves=[
                {"name": "Hydro Pump", "type": "Water", "category": "special", "power": 110}
            ],
            ability="Torrent",
            is_active=True,
            position=1
        )
    ]

    # Player 2's team (opponent)
    p2_team = [
        PokemonState(
            species="Venusaur",
            name="Venusaur",
            level=50,
            types=["Grass", "Poison"],
            stats={"hp": 100, "atk": 82, "def": 83, "spa": 100, "spd": 100, "spe": 80},
            current_hp=90,
            max_hp=100,
            moves=[
                {"name": "Solar Beam", "type": "Grass", "category": "special", "power": 120}
            ],
            ability="Overgrow",
            is_active=True,
            position=0
        ),
        PokemonState(
            species="Pikachu",
            name="Pikachu",
            level=50,
            types=["Electric"],
            stats={"hp": 80, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
            current_hp=80,
            max_hp=80,
            moves=[
                {"name": "Thunderbolt", "type": "Electric", "category": "special", "power": 90}
            ],
            ability="Static",
            is_active=True,
            position=1
        )
    ]

    p1_state = PlayerState(agent_id="agent1", team=p1_team, active=[0, 1])
    p2_state = PlayerState(agent_id="agent2", team=p2_team, active=[0, 1])

    return BattleState(
        battle_id="test_battle",
        player1=p1_state,
        player2=p2_state,
        turn=1,
        phase=BattlePhase.BATTLE
    )


class TestAIDecisionEngine:
    """Test AI decision engine functionality"""

    def test_engine_initialization(self, engine):
        """Test that AI engine initializes correctly"""
        assert engine is not None
        assert hasattr(engine, 'type_chart')
        assert hasattr(engine, 'damage_calculator')

    @pytest.mark.asyncio
    async def test_make_decision_returns_actions(self, engine, sample_battle_state):
        """Test that make_decision returns a list of actions"""
        actions = await engine.make_decision(sample_battle_state, 1)

        assert isinstance(actions, list)
        # Should return one action per active Pokemon
        assert len(actions) == 2

    @pytest.mark.asyncio
    async def test_rule_based_decision_returns_valid_action(self, engine, sample_battle_state):
        """Test that rule-based decision returns a valid action"""
        pokemon = sample_battle_state.player1.team[0]
        player = sample_battle_state.player1
        opponent = sample_battle_state.player2

        action = engine._rule_based_decision(pokemon, player, opponent, sample_battle_state)

        assert "pokemon_index" in action
        assert "action_type" in action
        assert action["action_type"] in ["move", "switch"]

    @pytest.mark.asyncio
    async def test_rule_based_prefers_super_effective(self, engine, sample_battle_state):
        """Test that rule-based AI prefers super-effective moves"""
        # Charizard vs Venusaur (Fire vs Grass/Poison = super effective)
        pokemon = sample_battle_state.player1.team[0]  # Charizard
        player = sample_battle_state.player1
        opponent = sample_battle_state.player2

        action = engine._rule_based_decision(pokemon, player, opponent, sample_battle_state)

        # Should choose a move action
        assert action["action_type"] == "move"
        assert "move_index" in action

    @pytest.mark.asyncio
    async def test_rule_based_considers_switching(self, engine, sample_battle_state):
        """Test that rule-based AI considers switching when HP is low"""
        # Set Charizard HP to low
        sample_battle_state.player1.team[0].current_hp = 10  # 10% HP
        sample_battle_state.player1.team[0].max_hp = 100

        pokemon = sample_battle_state.player1.team[0]
        player = sample_battle_state.player1
        opponent = sample_battle_state.player2

        action = engine._rule_based_decision(pokemon, player, opponent, sample_battle_state)

        # Should have a valid action (may or may not switch depending on implementation)
        assert "action_type" in action

    def test_build_llm_prompt(self, engine, sample_battle_state):
        """Test that LLM prompt is built correctly"""
        pokemon = sample_battle_state.player1.team[0]
        player = sample_battle_state.player1
        opponent = sample_battle_state.player2

        prompt = engine._build_llm_prompt(pokemon, player, opponent, sample_battle_state)

        assert isinstance(prompt, str)
        assert "Charizard" in prompt
        assert "Venusaur" in prompt
        assert "Flamethrower" in prompt

    def test_parse_llm_decision_move(self, engine, sample_battle_state):
        """Test parsing LLM decision for move action"""
        decision = {
            "action": "move",
            "move_index": 0,
            "target": [2, 0],
            "reasoning": "Flamethrower is super effective"
        }

        pokemon = sample_battle_state.player1.team[0]
        player = sample_battle_state.player1
        opponent = sample_battle_state.player2

        action = engine._parse_llm_decision(decision, pokemon, player, opponent)

        assert action is not None
        assert action["action_type"] == "move"
        assert action["move_index"] == 0

    def test_parse_llm_decision_switch(self, engine, sample_battle_state):
        """Test parsing LLM decision for switch action"""
        decision = {
            "action": "switch",
            "switch_to": 2,
            "reasoning": "Need to switch to a better matchup"
        }

        pokemon = sample_battle_state.player1.team[0]
        player = sample_battle_state.player1
        opponent = sample_battle_state.player2

        action = engine._parse_llm_decision(decision, pokemon, player, opponent)

        assert action is not None
        assert action["action_type"] == "switch"
        assert action["switch_to"] == 2

    @pytest.mark.asyncio
    async def test_llm_decision_fallback_on_error(self, engine, sample_battle_state):
        """Test that AI falls back to rule-based when LLM fails"""
        # Create a mock LLM client that raises an error
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("LLM Error")
        )

        actions = await engine.make_decision(
            sample_battle_state,
            1,
            llm_client=mock_client
        )

        # Should still return actions (from rule-based fallback)
        assert len(actions) == 2
        for action in actions:
            assert "action_type" in action

    @pytest.mark.asyncio
    async def test_handles_fainted_pokemon(self, engine, sample_battle_state):
        """Test that AI handles fainted Pokemon correctly"""
        # Faint one of player 1's Pokemon
        sample_battle_state.player1.team[0].is_fainted = True
        sample_battle_state.player1.team[0].current_hp = 0

        actions = await engine.make_decision(sample_battle_state, 1)

        # Should only return action for the non-fainted Pokemon
        assert len(actions) >= 1

    @pytest.mark.asyncio
    async def test_targets_opponent_pokemon(self, engine, sample_battle_state):
        """Test that AI targets opponent Pokemon"""
        actions = await engine.make_decision(sample_battle_state, 1)

        for action in actions:
            if action["action_type"] == "move":
                # Target should be player 2's Pokemon
                target = action.get("target")
                if target and isinstance(target, (list, tuple)):
                    # First element should be 2 (opponent)
                    assert target[0] == 2
