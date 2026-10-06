import math
import pytest
from config import settings as cfg
from models.speed_optimizer import SpeedOptimizer


@pytest.mark.parametrize("current,future", [(0, 0), (-20, 20), (20, -20), (float('nan'), 0)])
def test_bounds(current, future):
    speed = SpeedOptimizer().recommend(14000, current, future)
    assert math.isfinite(speed)
    assert cfg.MIN_SPEED_KMH <= speed <= cfg.MAX_SPEED_KMH


def test_prediction_changes_optimum():
    opt = SpeedOptimizer()
    assert opt.recommend(14000, 0, 12) < opt.recommend(14000, 0, 0)
