import numpy as np
import pytest
from services.route_processor import RouteProcessor


@pytest.fixture
def route():
    points = RouteProcessor.resample([[11, 47], [11.3, 47.1]])
    distance = points.total_distance_m.to_numpy()
    return RouteProcessor.with_elevation(points, 600 + 30 * np.sin(distance / 900) + .01 * distance)
