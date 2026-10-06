import numpy as np
import pytest
from config import settings as cfg
from services.route_processor import RouteProcessor as RP, haversine
from simulation.vehicle_simulator import VehicleSimulator
from models.curve_speed import CurveSpeedProfile


def test_straight_road_unrestricted():
    geometry = np.array([[39., 44.], [39., 44.03]])
    profile = CurveSpeedProfile.from_geometry(geometry, np.array([0, 3335.]))
    assert np.allclose(profile.local_limit_kmh, cfg.MAX_SPEED_KMH)


def test_radius_controls_speed():
    radius = 100
    angle = np.linspace(0, np.pi / 2, 201)
    metres_per_degree = 6371008.8 * np.pi / 180
    geometry = np.column_stack((39 + radius * np.cos(angle) / (metres_per_degree * np.cos(np.radians(44))),
                                44 + radius * np.sin(angle) / metres_per_degree))
    distances = np.r_[0, np.cumsum(haversine(geometry[:-1, 1], geometry[:-1, 0], geometry[1:, 1], geometry[1:, 0]))]
    profile = CurveSpeedProfile.from_geometry(geometry, distances)
    expected = np.sqrt(cfg.MAX_LATERAL_ACCELERATION_M_S2 * radius) * 3.6
    assert profile.local_limit_kmh[len(profile.local_limit_kmh) // 2] == pytest.approx(expected, rel=.02)


@pytest.mark.parametrize("ai", [True, False])
def test_brakes_before_turn_and_accelerates_after(ai):
    geometry = [[39., 44.], [39.02, 44.], [39.02, 44.02]]
    frame = RP.resample(geometry)
    frame = RP.with_elevation(frame, np.zeros(len(frame)))
    sim = VehicleSimulator(frame, geometry=geometry)
    sim.ai_control = ai
    sim.manual_speed_kmh = 80
    turn = float(haversine(44, 39, 44, 39.02))
    sim.start()
    records = []
    for _ in range(3000):
        before_v, before_t = sim.state.speed_kmh, sim.state.simulation_time_s
        sim.step(.2)
        state = sim.state
        dt = state.simulation_time_s - before_t
        assert -cfg.DECELERATION_M_S2 - .001 <= (state.speed_kmh - before_v) / 3.6 / dt <= cfg.ACCELERATION_M_S2 + .001
        records.append((state.current_distance_m, state.speed_kmh))
        if state.current_distance_m > turn + 800:
            break
    d, v = np.array(records).T
    cruising = np.max(v[(d > turn - 600) & (d < turn - 400)])
    assert np.min(v[(d > turn - 100) & (d < turn - 30)]) < cruising - 10
    assert np.min(v[np.abs(d - turn) < 20]) < 35
    assert np.max(v[(d > turn + 500) & (d < turn + 800)]) > cruising - 2
