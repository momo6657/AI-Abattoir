"""
Tests for Pokemon type effectiveness system
"""

import pytest
from app.services.pokemon.type_chart import TypeChart, get_type_effectiveness


class TestTypeChart:
    """Test type effectiveness calculations"""

    def test_normal_effectiveness(self):
        """Test normal effectiveness (1.0x)"""
        # Normal vs Normal = 1.0x
        assert TypeChart.get_effectiveness("Normal", "Normal") == 1.0
        # Fire vs Normal = 1.0x
        assert TypeChart.get_effectiveness("Fire", "Normal") == 1.0

    def test_super_effective(self):
        """Test super effective (2.0x)"""
        # Fire vs Grass = 2.0x
        assert TypeChart.get_effectiveness("Fire", "Grass") == 2.0
        # Water vs Fire = 2.0x
        assert TypeChart.get_effectiveness("Water", "Fire") == 2.0
        # Electric vs Water = 2.0x
        assert TypeChart.get_effectiveness("Electric", "Water") == 2.0

    def test_not_very_effective(self):
        """Test not very effective (0.5x)"""
        # Fire vs Water = 0.5x
        assert TypeChart.get_effectiveness("Fire", "Water") == 0.5
        # Water vs Grass = 0.5x
        assert TypeChart.get_effectiveness("Water", "Grass") == 0.5
        # Electric vs Grass = 0.5x
        assert TypeChart.get_effectiveness("Electric", "Grass") == 0.5

    def test_no_effect(self):
        """Test no effect (0.0x)"""
        # Normal vs Ghost = 0.0x
        assert TypeChart.get_effectiveness("Normal", "Ghost") == 0.0
        # Ghost vs Normal = 0.0x
        assert TypeChart.get_effectiveness("Ghost", "Normal") == 0.0
        # Electric vs Ground = 0.0x
        assert TypeChart.get_effectiveness("Electric", "Ground") == 0.0

    def test_dual_type_effectiveness(self):
        """Test dual type effectiveness"""
        # Fire vs Grass/Steel = 2.0x * 2.0x = 4.0x
        assert TypeChart.get_dual_type_effectiveness("Fire", ["Grass", "Steel"]) == 4.0
        # Water vs Fire/Water = 2.0x * 0.5x = 1.0x
        assert TypeChart.get_dual_type_effectiveness("Water", ["Fire", "Water"]) == 1.0
        # Electric vs Water/Flying = 2.0x * 2.0x = 4.0x
        assert TypeChart.get_dual_type_effectiveness("Electric", ["Water", "Flying"]) == 4.0

    def test_dual_type_no_effect(self):
        """Test dual type with immunity"""
        # Normal vs Ghost/Steel = 1.0x * 0.0x = 0.0x
        assert TypeChart.get_dual_type_effectiveness("Normal", ["Ghost", "Steel"]) == 0.0
        # Electric vs Water/Ground = 2.0x * 0.0x = 0.0x
        assert TypeChart.get_dual_type_effectiveness("Electric", ["Water", "Ground"]) == 0.0

    def test_empty_defense_types(self):
        """Test with empty defense types"""
        assert TypeChart.get_dual_type_effectiveness("Fire", []) == 1.0

    def test_invalid_attack_type(self):
        """Test with invalid attack type"""
        assert TypeChart.get_effectiveness("Invalid", "Fire") == 1.0
        assert TypeChart.get_dual_type_effectiveness("Invalid", ["Fire", "Water"]) == 1.0

    def test_get_all_effectiveness(self):
        """Test getting all effectiveness for an attack type"""
        fire_effectiveness = TypeChart.get_all_effectiveness("Fire")
        assert fire_effectiveness["Grass"] == 2.0
        assert fire_effectiveness["Water"] == 0.5
        assert fire_effectiveness["Ice"] == 2.0

    def test_convenience_function(self):
        """Test the convenience function"""
        assert get_type_effectiveness("Fire", ["Grass"]) == 2.0
        assert get_type_effectiveness("Fire", ["Grass", "Steel"]) == 4.0
