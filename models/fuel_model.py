"""Quasi-static longitudinal diesel model, separate from ML."""
from dataclasses import dataclass
import math
from config import settings as cfg


@dataclass(frozen=True)
class FuelResult:
    fuel_l_h: float
    fuel_l_per_100km: float | None
    traction_power_kw: float
    rolling_force_n: float
    grade_force_n: float
    air_force_n: float


class FuelModel:
    def calculate(self, speed_kmh: float, mass_kg: float, slope_pct: float,
                  acceleration_m_s2: float = 0.0) -> FuelResult:
        if not all(math.isfinite(v) for v in (speed_kmh, mass_kg, slope_pct, acceleration_m_s2)):
            raise ValueError("Параметры расхода должны быть конечными числами")
        if speed_kmh < 0 or mass_kg <= 0:
            raise ValueError("Скорость не может быть отрицательной; масса должна быть положительной")
        v = speed_kmh / 3.6
        theta = math.atan(slope_pct / 100)
        rolling = mass_kg * cfg.GRAVITY * cfg.ROLLING_RESISTANCE * math.cos(theta)
        grade = mass_kg * cfg.GRAVITY * math.sin(theta)
        air = 0.5 * cfg.AIR_DENSITY * cfg.DRAG_COEFFICIENT * cfg.FRONTAL_AREA_M2 * v * v
        power = max(0.0, (rolling + grade + air + mass_kg * acceleration_m_s2) * v / 1000)
        fuel = cfg.IDLE_FUEL_L_H + power / (cfg.ENGINE_EFFICIENCY * cfg.DIESEL_ENERGY_KWH_PER_L)
        return FuelResult(fuel, fuel * 100 / speed_kmh if speed_kmh >= 1 else None,
                          power, rolling, grade, air)
