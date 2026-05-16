import pytest


def test_elo_basic():
    """Test basic Elo calculation logic."""
    # Simple Elo test: higher rated player wins
    ra, rb = 1500, 1500
    sa = 1.0  # player A wins
    k = 32
    ea = 1 / (1 + 10 ** ((rb - ra) / 400))
    new_ra = ra + k * (sa - ea)
    new_rb = rb + k * ((1 - sa) - (1 - ea))

    assert new_ra > ra  # winner gains points
    assert new_rb < rb  # loser loses points
    assert abs(new_ra - 1516) < 1  # expected ~1516
    assert abs(new_rb - 1484) < 1  # expected ~1484


def test_elo_draw():
    """Test Elo with a draw."""
    ra, rb = 1500, 1500
    sa = 0.5  # draw
    k = 32
    ea = 1 / (1 + 10 ** ((rb - ra) / 400))
    new_ra = ra + k * (sa - ea)
    new_rb = rb + k * ((1 - sa) - (1 - ea))

    assert abs(new_ra - 1500) < 0.01  # no change
    assert abs(new_rb - 1500) < 0.01


def test_elo_upset():
    """Test Elo when lower rated player wins."""
    ra, rb = 1200, 1800
    sa = 1.0  # lower rated wins
    k = 32
    ea = 1 / (1 + 10 ** ((rb - ra) / 400))
    new_ra = ra + k * (sa - ea)

    # Lower rated player should gain more points than in an even match
    assert new_ra - ra > 25
