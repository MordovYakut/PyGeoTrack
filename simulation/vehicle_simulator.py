from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from config import settings as cfg
from services.route_processor import RouteProcessor, haversine
from services.can_simulator import CANSimulator
from models.fuel_model import FuelModel
from models.speed_optimizer import SpeedOptimizer
from models.curve_speed import CurveSpeedProfile


@dataclass
class VehicleState:
    simulation_time_s: float = 0.0
    current_distance_m: float = 0.0
    speed_kmh: float = 0.0
    fuel_used_l: float = 0.0
    fuel_l_h: float = 0.0
    fuel_l_per_100km: float | None = None
    latitude: float = 0.0
    longitude: float = 0.0
    elevation_m: float = 0.0
    slope_pct: float = 0.0
    predicted_slope_pct: float | None = None
    recommended_speed_kmh: float = cfg.DEFAULT_SPEED_KMH
    completed: bool = False
    curve_speed_limit_kmh: float = cfg.MAX_SPEED_KMH


@dataclass(frozen=True)
class SimulationSummary:
    travel_time_s: float
    distance_km: float
    fuel_used_l: float
    average_fuel_l_100km: float
    average_speed_kmh: float


class VehicleSimulator:
    """Time-based integration with bounded acceleration and exact end clipping."""
    def __init__(self, route: pd.DataFrame, can: CANSimulator | None = None,
                 geometry: list | None = None):
        self.route = RouteProcessor.validate(route)
        self.distances = self.route.total_distance_m.to_numpy()
        self.length_m = float(self.distances[-1])
        self.can = can or CANSimulator()
        self.fuel = FuelModel()
        self.optimizer = SpeedOptimizer()
        self.ai_control = True
        self.manual_speed_kmh = cfg.DEFAULT_SPEED_KMH
        self.running = False
        self.geometry = np.asarray(geometry if geometry is not None else route[["longitude", "latitude"]], float)
        self.geometry_distances = np.r_[0, np.cumsum(haversine(
            self.geometry[:-1, 1], self.geometry[:-1, 0], self.geometry[1:, 1], self.geometry[1:, 0]))]
        self.geometry_distances *= self.length_m / self.geometry_distances[-1]
        self.curves = CurveSpeedProfile.from_geometry(self.geometry, self.geometry_distances)
        # The optimization grid is evaluated once per route point, never in the UI timer.
        predicted = self.route.get("predicted_slope_pct", self.route.slope_pct).to_numpy()
        predicted = np.where(self.distances + cfg.PREDICTION_DISTANCE_M <= self.length_m,
                             predicted, self.route.slope_pct.to_numpy())
        mass = self.can.get_current_data().total_mass_kg
        self.targets = np.array([self.optimizer.recommend(mass, float(s), float(p))
                                 for s, p in zip(self.route.slope_pct, predicted)])
        self.reset()

    def reset(self) -> VehicleState:
        self.running = False
        self._braking_for_end = False
        self.can.reset()
        self.state = VehicleState(recommended_speed_kmh=float(self.targets[0]))
        self._position()
        self.state.recommended_speed_kmh = min(self.state.recommended_speed_kmh, self.state.curve_speed_limit_kmh)
        return self.state

    def start(self) -> None:
        if not self.state.completed:
            self.running = True

    def pause(self) -> None:
        self.running = False

    def _position(self) -> None:
        s = self.state
        p = RouteProcessor.position(self.route, s.current_distance_m)
        s.longitude = float(np.interp(s.current_distance_m, self.geometry_distances, self.geometry[:, 0]))
        s.latitude = float(np.interp(s.current_distance_m, self.geometry_distances, self.geometry[:, 1]))
        s.elevation_m, s.slope_pct = p.elevation_m, p.slope_pct
        s.curve_speed_limit_kmh = self.curves.speed_at(s.current_distance_m)
        s.predicted_slope_pct = None
        if s.current_distance_m + cfg.PREDICTION_DISTANCE_M <= self.length_m:
            s.predicted_slope_pct = float(np.interp(s.current_distance_m, self.distances,
                self.route.get("predicted_slope_pct", self.route.slope_pct)))

    def step(self, dt: float) -> VehicleState:
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Шаг времени должен быть конечным и неотрицательным")
        if not self.running or self.state.completed or dt == 0:
            return self.state
        s = self.state
        remaining_time = dt
        while remaining_time > 1e-9 and not s.completed:
            h = min(0.2, remaining_time)
            recommendation = float(np.interp(s.current_distance_m, self.distances, self.targets))
            curve_limit = self.curves.speed_at(s.current_distance_m)
            recommendation = min(recommendation, curve_limit)
            s.recommended_speed_kmh += float(np.clip(recommendation - s.recommended_speed_kmh,
                -cfg.RECOMMENDATION_CHANGE_KMH_S * h, cfg.RECOMMENDATION_CHANGE_KMH_S * h))
            target = s.recommended_speed_kmh if self.ai_control else self.manual_speed_kmh
            # Curves apply in both manual and AI mode, including below the cruise minimum.
            target = min(float(np.clip(target, cfg.MIN_CURVE_SPEED_KMH, cfg.MAX_SPEED_KMH)),
                         self.curves.speed_at(s.current_distance_m + s.speed_kmh / 3.6 * h)) / 3.6
            remaining_distance = self.length_m - s.current_distance_m
            target = min(target, math.sqrt(2 * cfg.DECELERATION_M_S2 * remaining_distance))
            old_v = s.speed_kmh / 3.6
            acceleration = float(np.clip((target - old_v) / h,
                                         -cfg.DECELERATION_M_S2, cfg.ACCELERATION_M_S2))
            # Begin a constant-deceleration approach early enough to stop at B without
            # an artificial speed snap on the final fractional integration step.
            stopping_distance = old_v ** 2 / (2 * cfg.DECELERATION_M_S2)
            lookahead = old_v * h * (1 + cfg.ACCELERATION_M_S2 / cfg.DECELERATION_M_S2) + cfg.ACCELERATION_M_S2 * h * h
            if old_v > 0 and remaining_distance <= stopping_distance + lookahead:
                self._braking_for_end = True
            if self._braking_for_end and remaining_distance > 0:
                acceleration = -old_v ** 2 / (2 * remaining_distance)
            new_v = max(0, old_v + acceleration * h)
            distance = (old_v + new_v) / 2 * h
            if distance >= remaining_distance:
                # Solve d = v*t + a*t²/2 for the partial final integration step.
                root = math.sqrt(max(0, old_v * old_v + 2 * acceleration * remaining_distance))
                h = 2 * remaining_distance / max(old_v + root, 1e-12)
                new_v = max(0, old_v + acceleration * h)
                distance = remaining_distance
                s.completed = True
            result = self.fuel.calculate((old_v + new_v) / 2 * 3.6,
                                         self.can.get_current_data().total_mass_kg,
                                         s.slope_pct, acceleration)
            s.fuel_used_l += result.fuel_l_h * h / 3600
            s.simulation_time_s += h
            s.current_distance_m = min(self.length_m, s.current_distance_m + distance)
            s.speed_kmh = 0 if s.completed else new_v * 3.6
            s.fuel_l_h = 0 if s.completed else result.fuel_l_h
            s.fuel_l_per_100km = None if s.completed else result.fuel_l_per_100km
            self._position()
            remaining_time -= h
        if s.completed:
            self.running = False
        self.can.record(s.speed_kmh, s.simulation_time_s)
        return s

    def passed_route(self) -> list:
        count = int(np.searchsorted(self.geometry_distances, self.state.current_distance_m, side="right"))
        points = self.geometry[:count, ::-1].tolist()
        position = [self.state.latitude, self.state.longitude]
        if not points or points[-1] != position:
            points.append(position)
        return points

    def summary(self) -> SimulationSummary:
        s = self.state
        km = s.current_distance_m / 1000
        return SimulationSummary(s.simulation_time_s, km, s.fuel_used_l,
                                 s.fuel_used_l / km * 100 if km else 0,
                                 km / s.simulation_time_s * 3600 if s.simulation_time_s else 0)
