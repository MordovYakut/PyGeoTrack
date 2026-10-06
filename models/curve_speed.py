"""Road-geometry speed limits, including a backward braking envelope."""
from dataclasses import dataclass
from functools import cached_property
import numpy as np
from config import settings as cfg


@dataclass(frozen=True)
class CurveSpeedProfile:
    distances_m: np.ndarray
    local_limit_kmh: np.ndarray
    approach_limit_kmh: np.ndarray

    @classmethod
    def from_geometry(cls, coordinates: np.ndarray, distances: np.ndarray) -> "CurveSpeedProfile":
        """Estimate curvature using 3 points 20 m apart on the full road polyline.

        A fixed spatial window suppresses short-segment GPS/OSM noise. Lateral
        acceleration gives v² <= a_lat / curvature. A backward pass makes braking
        start before the curve; speed can rise again after the turn clears.
        """
        samples = np.r_[np.arange(0, distances[-1], cfg.CURVE_SAMPLE_STEP_M), distances[-1]]
        lat = np.radians(coordinates[:, 1])
        lon = np.unwrap(np.radians(coordinates[:, 0]))
        # Local tangent projection, used only for curvature (route distance remains Haversine).
        x = (lon - lon[0]) * 6371008.8 * np.cos(np.mean(lat))
        y = (lat - lat[0]) * 6371008.8
        points = []
        for offset in (-cfg.CURVE_WINDOW_M, 0, cfg.CURVE_WINDOW_M):
            points.append(np.column_stack((np.interp(samples + offset, distances, x),
                                           np.interp(samples + offset, distances, y))))
        before, middle, after = points
        a, b, chord = middle - before, after - middle, after - before
        denominator = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) * np.linalg.norm(chord, axis=1)
        cross = np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])
        curvature = np.divide(2 * cross, denominator, out=np.zeros_like(cross), where=denominator > 1e-6)
        speed_squared = np.minimum((cfg.MAX_SPEED_KMH / 3.6) ** 2,
            cfg.MAX_LATERAL_ACCELERATION_M_S2 / np.maximum(curvature, 1e-9))
        speed_squared = np.maximum(speed_squared, (cfg.MIN_CURVE_SPEED_KMH / 3.6) ** 2)
        local = np.sqrt(speed_squared) * 3.6
        allowed = speed_squared.copy()
        for i in range(len(samples) - 2, -1, -1):
            allowed[i] = min(allowed[i], allowed[i + 1] + 2 * cfg.CURVE_BRAKING_M_S2 * (samples[i + 1] - samples[i]))
        return cls(samples, local, np.sqrt(allowed) * 3.6)

    @cached_property
    def speed_squared(self) -> np.ndarray:
        return (self.approach_limit_kmh / 3.6) ** 2

    def speed_at(self, distance_m: float) -> float:
        # Squared-speed interpolation preserves the braking-distance equation between samples.
        squared = np.interp(distance_m, self.distances_m, self.speed_squared)
        return float(np.sqrt(squared) * 3.6)
