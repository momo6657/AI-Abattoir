import pytest

from app.services.evolution_service import EvolutionService
from app.models.agent import AgentLevel


service = EvolutionService()


class TestLevelFromXp:
    def test_zero_xp_is_novice(self):
        assert service._level_from_xp(0) == AgentLevel.NOVICE

    def test_below_proficient_threshold(self):
        assert service._level_from_xp(50) == AgentLevel.NOVICE
        assert service._level_from_xp(99) == AgentLevel.NOVICE

    def test_proficient(self):
        assert service._level_from_xp(100) == AgentLevel.PROFICIENT
        assert service._level_from_xp(250) == AgentLevel.PROFICIENT

    def test_expert(self):
        assert service._level_from_xp(500) == AgentLevel.EXPERT
        assert service._level_from_xp(999) == AgentLevel.EXPERT

    def test_master(self):
        assert service._level_from_xp(1500) == AgentLevel.MASTER
        assert service._level_from_xp(10000) == AgentLevel.MASTER

    def test_exact_boundary_values(self):
        assert service._level_from_xp(100) == AgentLevel.PROFICIENT
        assert service._level_from_xp(500) == AgentLevel.EXPERT
        assert service._level_from_xp(1500) == AgentLevel.MASTER

    def test_just_below_boundary(self):
        assert service._level_from_xp(99) == AgentLevel.NOVICE
        assert service._level_from_xp(499) == AgentLevel.PROFICIENT
        assert service._level_from_xp(1499) == AgentLevel.EXPERT


class TestNextLevelXp:
    def test_novice_next_level(self):
        assert service._next_level_xp(0) == 100
        assert service._next_level_xp(50) == 100

    def test_proficient_next_level(self):
        assert service._next_level_xp(100) == 500
        assert service._next_level_xp(300) == 500

    def test_expert_next_level(self):
        assert service._next_level_xp(500) == 1500
        assert service._next_level_xp(1000) == 1500

    def test_master_no_next_level(self):
        assert service._next_level_xp(1500) is None
        assert service._next_level_xp(99999) is None


class TestCalcProgress:
    def test_zero_progress(self):
        assert service._calc_progress(0) == 0.0

    def test_full_progress_at_master(self):
        assert service._calc_progress(1500) == 1.0
        assert service._calc_progress(99999) == 1.0

    def test_mid_progress(self):
        # At 300 XP: range 100-500, progress = (300-100)/(500-100) = 0.5
        progress = service._calc_progress(300)
        assert abs(progress - 0.5) < 0.01

    def test_progress_between_zero_and_one(self):
        for xp in [0, 50, 100, 250, 500, 750, 1500]:
            p = service._calc_progress(xp)
            assert 0.0 <= p <= 1.0, f"Progress for xp={xp} is {p}, expected 0-1"


class TestCalculateXp:
    def test_conversation_base_range(self):
        for _ in range(20):
            xp = service._calculate_xp("conversation", "completed")
            assert 5 <= xp <= 20

    def test_arena_pk_base_range(self):
        for _ in range(20):
            xp = service._calculate_xp("arena_pk", "completed")
            assert 10 <= xp <= 50

    def test_game_base_range(self):
        for _ in range(20):
            xp = service._calculate_xp("game", "completed")
            assert 20 <= xp <= 100

    def test_win_bonus(self):
        # Win gives 1.5x multiplier. Base range for conversation: 5-20.
        # With bonus: 7-30 (int(xp * 1.5)).
        # Just verify it's higher than non-win in most cases.
        win_xps = [service._calculate_xp("game", "win") for _ in range(50)]
        normal_xps = [service._calculate_xp("game", "completed") for _ in range(50)]
        assert min(win_xps) >= min(normal_xps)

    def test_unknown_scene_type_defaults(self):
        for _ in range(20):
            xp = service._calculate_xp("unknown_type", "done")
            assert 5 <= xp <= 20
