import math
import numpy as np
from config import settings as cfg
from models.fuel_model import FuelModel


class SpeedOptimizer:
    """Discrete fuel/time search with an anticipatory engine-load penalty."""
    def __init__(self):
        self.fuel = FuelModel()

    def recommend(self, mass_kg: float, current_slope: float, predicted_slope: float) -> float:
        if not all(math.isfinite(v) for v in (mass_kg, current_slope, predicted_slope)):
            return cfg.DEFAULT_SPEED_KMH
        if mass_kg <= 0:
            raise ValueError("Масса автомобиля должна быть положительной")
        speeds = np.arange(cfg.MIN_SPEED_KMH, cfg.MAX_SPEED_KMH + 1)
        costs = []
        for speed in speeds:
            now = self.fuel.calculate(float(speed), mass_kg, current_slope)
            ahead = self.fuel.calculate(float(speed), mass_kg, predicted_slope)
            consumption = 0.4 * now.fuel_l_per_100km + 0.6 * ahead.fuel_l_per_100km
            fuel_cost = consumption / cfg.FUEL_REFERENCE_L_100KM
            time_cost = cfg.LAMBDA_TIME * cfg.DEFAULT_SPEED_KMH / speed
            power_cost = cfg.POWER_PENALTY * max(0, ahead.traction_power_kw / cfg.MAX_TRACTION_POWER_KW - 1) ** 2
            costs.append(fuel_cost + time_cost + power_cost)
        return float(speeds[np.argmin(costs)])
