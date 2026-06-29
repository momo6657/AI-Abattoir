"""Tests for the Elo rating system."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.pokemon.elo_rating import EloRatingService, EloResult


@pytest.fixture
def elo():
    return EloRatingService()


class TestExpectedScore:
    def test_equal_ratings(self, elo):
        assert elo.expected_score(1500, 1500) == pytest.approx(0.5)

    def test_higher_rating_favored(self, elo):
        assert elo.expected_score(1800, 1500) > 0.5
        assert elo.expected_score(1500, 1800) < 0.5

    def test_extreme_difference(self, elo):
        # 800-point gap → expected ~0.99
        assert elo.expected_score(2300, 1500) > 0.95
        assert elo.expected_score(1500, 2300) < 0.05

    def test_symmetry(self, elo):
        e1 = elo.expected_score(1600, 1400)
        e2 = elo.expected_score(1400, 1600)
        assert e1 + e2 == pytest.approx(1.0)


class TestKFactor:
    def test_provisional(self, elo):
        assert elo.k_factor(0) == 40
        assert elo.k_factor(29) == 40

    def test_standard(self, elo):
        assert elo.k_factor(30) == 20
        assert elo.k_factor(99) == 20

    def test_established(self, elo):
        assert elo.k_factor(100) == 10
        assert elo.k_factor(500) == 10


class TestCalculateElo:
    def test_equal_ratings_p1_wins(self, elo):
        result = elo.calculate_elo(1500, 1500, 1.0, 50, 50)
        assert result.player1_new > 1500
        assert result.player2_new < 1500
        assert result.player1_change == -result.player2_change

    def test_draw_equal_ratings(self, elo):
        result = elo.calculate_elo(1500, 1500, 0.5, 50, 50)
        assert result.player1_new == 1500
        assert result.player2_new == 1500
        assert result.player1_change == 0

    def test_underdog_wins_bigger_gain(self, elo):
        # Lower-rated player wins → bigger gain
        result_underdog = elo.calculate_elo(1200, 1800, 1.0, 50, 50)
        result_favorite = elo.calculate_elo(1800, 1200, 1.0, 50, 50)
        assert result_underdog.player1_change > result_favorite.player1_change

    def test_provisional_player_moves_more(self, elo):
        result_new = elo.calculate_elo(1500, 1500, 1.0, 5, 50)
        result_exp = elo.calculate_elo(1500, 1500, 1.0, 200, 200)
        assert abs(result_new.player1_change) > abs(result_exp.player1_change)

    def test_rating_bounds(self, elo):
        # Can't go below 100
        result = elo.calculate_elo(100, 1500, 0.0, 50, 50)
        assert result.player1_new >= 100

        # Can't go above 4000
        result = elo.calculate_elo(4000, 1500, 1.0, 50, 50)
        assert result.player1_new <= 4000

    def test_expected_score_range(self, elo):
        result = elo.calculate_elo(1600, 1400, 1.0, 50, 50)
        assert 0 <= result.player1_expected <= 1
        assert 0 <= result.player2_expected <= 1

    def test_result_structure(self, elo):
        result = elo.calculate_elo(1500, 1500, 1.0, 50, 50)
        assert isinstance(result, EloResult)
        assert result.k_factor > 0
        assert result.player1_old == 1500
        assert result.player2_old == 1500


class TestTierForRating:
    def test_grandmaster(self, elo):
        en, zh = elo.tier_for_rating(2300)
        assert en == "Grandmaster"
        assert zh == "宗师"

    def test_master(self, elo):
        en, zh = elo.tier_for_rating(2100)
        assert en == "Master"
        assert zh == "大师"

    def test_diamond(self, elo):
        en, zh = elo.tier_for_rating(1900)
        assert en == "Diamond"
        assert zh == "钻石"

    def test_platinum(self, elo):
        en, zh = elo.tier_for_rating(1700)
        assert en == "Platinum"
        assert zh == "铂金"

    def test_gold(self, elo):
        en, zh = elo.tier_for_rating(1500)
        assert en == "Gold"
        assert zh == "黄金"

    def test_silver(self, elo):
        en, zh = elo.tier_for_rating(1300)
        assert en == "Silver"
        assert zh == "白银"

    def test_bronze(self, elo):
        en, zh = elo.tier_for_rating(1100)
        assert en == "Bronze"
        assert zh == "青铜"

    def test_boundary_values(self, elo):
        assert elo.tier_for_rating(2200)[0] == "Grandmaster"
        assert elo.tier_for_rating(2199)[0] == "Master"
        assert elo.tier_for_rating(2000)[0] == "Master"
        assert elo.tier_for_rating(1999)[0] == "Diamond"


@pytest.mark.asyncio
async def test_leaderboard_format_filter_is_applied_to_query(elo):
    db = AsyncMock()
    result = MagicMock()
    result.scalars().all.return_value = []
    db.execute.return_value = result

    leaderboard = await elo.get_pokemon_leaderboard(
        db,
        format_filter="gen9ou",
        limit=10,
    )

    statement = db.execute.await_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert leaderboard == []
    assert "pokemon_battles" in compiled
    assert "gen9ou" in compiled
    assert "player1_agent_id" in compiled
    assert "player2_agent_id" in compiled
