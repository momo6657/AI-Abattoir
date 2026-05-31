"""
Tests for Pokemon damage calculator
"""

import pytest
from app.services.pokemon.damage_calculator import DamageCalculator, calculate_damage


class TestDamageCalculator:
    """Test damage calculation"""

    def test_physical_damage_basic(self):
        """Test basic physical damage calculation"""
        attacker = {
            "level": 50,
            "atk": 100,
        }
        defender = {
            "hp": 100,
            "def": 100,
        }
        move = {
            "power": 80,
            "type": "Normal",
            "category": "physical",
        }

        # Use fixed random factor for testing
        damage = DamageCalculator.calculate_damage(
            attacker, defender, move, random_factor=1.0
        )

        # Damage should be positive
        assert damage > 0

        # Formula: ((2 * 50 / 5 + 2) * 80 * 100 / 100) / 50 + 2 = 22 * 80 / 50 + 2 = 35.2 + 2 = 37.2
        # With random_factor=1.0, should be around 37
        assert damage == 37

    def test_special_damage_basic(self):
        """Test basic special damage calculation"""
        attacker = {
            "level": 50,
            "spa": 100,
        }
        defender = {
            "hp": 100,
            "spd": 100,
        }
        move = {
            "power": 90,
            "type": "Fire",
            "category": "special",
        }

        damage = DamageCalculator.calculate_damage(
            attacker, defender, move, random_factor=1.0
        )

        assert damage > 0
        # Formula: ((2 * 50 / 5 + 2) * 90 * 100 / 100) / 50 + 2 = 22 * 90 / 50 + 2 = 39.6 + 2 = 41.6
        assert damage == 41

    def test_status_move_zero_damage(self):
        """Test that status moves deal 0 damage"""
        attacker = {"level": 50, "atk": 100}
        defender = {"hp": 100, "def": 100}
        move = {
            "power": 0,
            "type": "Normal",
            "category": "status",
        }

        damage = DamageCalculator.calculate_damage(attacker, defender, move)
        assert damage == 0

    def test_type_effectiveness_super_effective(self):
        """Test super effective damage (2x)"""
        attacker = {"level": 50, "atk": 100}
        defender = {"hp": 100, "def": 100}
        move = {"power": 80, "type": "Fire", "category": "physical"}

        damage = DamageCalculator.calculate_damage(
            attacker, defender, move, type_effectiveness=2.0, random_factor=1.0
        )

        # Should be 2x the normal damage
        normal_damage = DamageCalculator.calculate_damage(
            attacker, defender, move, type_effectiveness=1.0, random_factor=1.0
        )
        assert damage == normal_damage * 2

    def test_type_effectiveness_not_very_effective(self):
        """Test not very effective damage (0.5x)"""
        attacker = {"level": 50, "atk": 100}
        defender = {"hp": 100, "def": 100}
        move = {"power": 80, "type": "Fire", "category": "physical"}

        damage = DamageCalculator.calculate_damage(
            attacker, defender, move, type_effectiveness=0.5, random_factor=1.0
        )

        # Should be 0.5x the normal damage
        normal_damage = DamageCalculator.calculate_damage(
            attacker, defender, move, type_effectiveness=1.0, random_factor=1.0
        )
        assert damage == int(normal_damage * 0.5)

    def test_stab_bonus(self):
        """Test STAB (Same Type Attack Bonus) - 1.5x damage"""
        attacker = {"level": 50, "atk": 100}
        defender = {"hp": 100, "def": 100}
        move = {"power": 80, "type": "Fire", "category": "physical"}

        damage_with_stab = DamageCalculator.calculate_damage(
            attacker, defender, move, stab=True, random_factor=1.0
        )

        damage_without_stab = DamageCalculator.calculate_damage(
            attacker, defender, move, stab=False, random_factor=1.0
        )

        # STAB should increase damage by 1.5x
        assert damage_with_stab == int(damage_without_stab * 1.5)

    def test_critical_hit(self):
        """Test critical hit - 1.5x damage"""
        attacker = {"level": 50, "atk": 100}
        defender = {"hp": 100, "def": 100}
        move = {"power": 80, "type": "Normal", "category": "physical"}

        damage_crit = DamageCalculator.calculate_damage(
            attacker, defender, move, critical=True, random_factor=1.0
        )

        damage_normal = DamageCalculator.calculate_damage(
            attacker, defender, move, critical=False, random_factor=1.0
        )

        # Critical hit should increase damage by 1.5x
        assert damage_crit == int(damage_normal * 1.5)

    def test_minimum_damage_is_one(self):
        """Test that minimum damage is 1"""
        attacker = {"level": 1, "atk": 1}
        defender = {"hp": 100, "def": 200}
        move = {"power": 1, "type": "Normal", "category": "physical"}

        damage = DamageCalculator.calculate_damage(
            attacker, defender, move, random_factor=0.85
        )

        # Even with worst stats, damage should be at least 1
        assert damage >= 1

    def test_random_factor_range(self):
        """Test that random factor affects damage"""
        attacker = {"level": 50, "atk": 100}
        defender = {"hp": 100, "def": 100}
        move = {"power": 80, "type": "Normal", "category": "physical"}

        damage_min = DamageCalculator.calculate_damage(
            attacker, defender, move, random_factor=0.85
        )

        damage_max = DamageCalculator.calculate_damage(
            attacker, defender, move, random_factor=1.0
        )

        # Damage with random_factor=0.85 should be less than with 1.0
        assert damage_min < damage_max

    def test_check_critical_stage_0(self):
        """Test critical hit check at stage 0 (1/24 chance)"""
        # This is probabilistic, so we just check it doesn't crash
        # and returns a boolean
        result = DamageCalculator.check_critical(0)
        assert isinstance(result, bool)

    def test_check_critical_stage_3_always_crits(self):
        """Test that stage 3+ always crits"""
        result = DamageCalculator.check_critical(3)
        assert result is True

        result = DamageCalculator.check_critical(4)
        assert result is True

    def test_check_move_hit_basic(self):
        """Test basic move accuracy check"""
        # This is probabilistic, so we just check it doesn't crash
        result = DamageCalculator.check_move_hit(100, 0, 0)
        assert isinstance(result, bool)

    def test_check_move_hit_accuracy_0_always_hits(self):
        """Test that accuracy 0 means always hit"""
        result = DamageCalculator.check_move_hit(0, 0, 0)
        assert result is True

    def test_convenience_function(self):
        """Test the convenience function"""
        attacker = {"level": 50, "atk": 100}
        defender = {"hp": 100, "def": 100}
        move = {"power": 80, "type": "Normal", "category": "physical"}

        damage = calculate_damage(attacker, defender, move)
        assert damage > 0
