import numpy as np
import pytest
from simulation.vehicle_simulator import VehicleSimulator
from services.can_simulator import CANSimulator


def test_pause_reset_and_acceleration(route, tmp_path):
    can = CANSimulator(tmp_path / "can.csv")
    sim = VehicleSimulator(route, can)
    sim.start()
    sim.step(1)
    assert sim.state.current_distance_m == pytest.approx(.5)
    assert sim.state.speed_kmh == pytest.approx(3.6)
    sim.pause()
    distance, fuel = sim.state.current_distance_m, sim.state.fuel_used_l
    sim.step(10)
    assert sim.state.current_distance_m == distance
    assert sim.state.fuel_used_l == fuel
    sim.reset()
    assert sim.state.current_distance_m == sim.state.fuel_used_l == sim.state.simulation_time_s == 0
    assert len(sim.passed_route()) == 1
    can.close()


def test_full_trip_and_exact_end(route):
    sim = VehicleSimulator(route.iloc[:15].copy())
    sim.start()
    for _ in range(500):
        sim.step(2)
        if sim.state.completed:
            break
    assert sim.state.completed
    assert not sim.running
    assert sim.state.speed_kmh == 0
    assert sim.state.current_distance_m == sim.length_m
    assert sim.state.latitude == route.iloc[14].latitude
    assert sim.state.longitude == route.iloc[14].longitude
    assert sim.summary().fuel_used_l > 0
    assert np.allclose(sim.passed_route(), route.iloc[:15][["latitude", "longitude"]])


def test_timestep_consistency(route):
    a, b = VehicleSimulator(route), VehicleSimulator(route)
    for sim in (a, b):
        sim.ai_control = False
        sim.start()
    for _ in range(100):
        a.step(.1)
    b.step(10)
    assert a.state.current_distance_m == pytest.approx(b.state.current_distance_m, abs=.01)
    assert a.state.fuel_used_l == pytest.approx(b.state.fuel_used_l, rel=.02)


def test_invalid_dt(route):
    with pytest.raises(ValueError):
        VehicleSimulator(route).step(float("nan"))


def test_endpoint_braking_respects_deceleration(route):
    sim = VehicleSimulator(route.iloc[:8].copy())
    sim.start()
    for _ in range(1000):
        old_speed = sim.state.speed_kmh / 3.6
        old_time = sim.state.simulation_time_s
        sim.step(.2)
        elapsed = sim.state.simulation_time_s - old_time
        if elapsed > 1e-6:
            acceleration = (sim.state.speed_kmh / 3.6 - old_speed) / elapsed
            assert -1.501 <= acceleration <= 1.001
        if sim.state.completed:
            break
    assert sim.state.completed
