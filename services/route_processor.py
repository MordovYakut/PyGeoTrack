"""Geodesic resampling and validated digital road profiles."""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from config import settings as cfg


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres, supporting numpy arrays."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 6371008.8 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


@dataclass(frozen=True)
class RoutePoint:
    latitude: float
    longitude: float
    elevation_m: float
    slope_pct: float
    total_distance_m: float


class RouteProcessor:
    @staticmethod
    def resample(coordinates: list, step_m: float = cfg.ROUTE_SAMPLE_STEP_M) -> pd.DataFrame:
        """Sample arc distance along the original polyline, including the exact endpoint."""
        coords = np.asarray(coordinates, dtype=float)
        if coords.ndim != 2 or coords.shape[1] != 2 or len(coords) < 2:
            raise ValueError("Для маршрута нужны как минимум две точки [долгота, широта]")
        if not np.isfinite(coords).all() or step_m <= 0 or not np.isfinite(step_m):
            raise ValueError("Неверная геометрия маршрута или шаг выборки")
        if (np.abs(coords[:, 0]) > 180).any() or (np.abs(coords[:, 1]) > 90).any():
            raise ValueError("Координаты вне допустимого диапазона WGS84")
        segments = haversine(coords[:-1, 1], coords[:-1, 0], coords[1:, 1], coords[1:, 0])
        keep = np.r_[True, segments > 1e-6]
        coords = coords[keep]
        if len(coords) < 2:
            raise ValueError("Маршрут имеет нулевую длину")
        segments = haversine(coords[:-1, 1], coords[:-1, 0], coords[1:, 1], coords[1:, 0])
        distances = np.r_[0, np.cumsum(segments)]
        if distances[-1] / step_m > cfg.MAX_ROUTE_POINTS:
            raise ValueError("Маршрут слишком длинный; увеличьте ROUTE_SAMPLE_STEP_M")
        samples = np.r_[np.arange(0, distances[-1], step_m), distances[-1]]
        # Unwrapped longitude supports routes crossing the antimeridian.
        longitudes = np.degrees(np.unwrap(np.radians(coords[:, 0])))
        lon = (np.interp(samples, distances, longitudes) + 180) % 360 - 180
        return pd.DataFrame({
            "point_id": np.arange(len(samples)),
            "latitude": np.interp(samples, distances, coords[:, 1]), "longitude": lon,
            "segment_distance_m": np.r_[0, np.diff(samples)], "total_distance_m": samples,
        })

    @staticmethod
    def slopes(route: pd.DataFrame) -> pd.DataFrame:
        result = route.copy()
        dz = result.elevation_m.diff().to_numpy()
        ds = result.segment_distance_m.to_numpy(float)
        slope = np.divide(dz * 100, ds, out=np.full(len(ds), np.nan), where=ds > 0)
        slope[0] = 0.0
        result["slope_raw_pct"] = slope
        # DEM measures terrain, not bridge/tunnel road surfaces. Keep raw values for audit.
        result["slope_pct"] = np.clip(slope, -cfg.MAX_SLOPE_PCT, cfg.MAX_SLOPE_PCT)
        result["slope_angle_deg"] = np.degrees(np.arctan(result.slope_pct / 100))
        return result

    @classmethod
    def with_elevation(cls, route: pd.DataFrame, heights: list) -> pd.DataFrame:
        if len(heights) != len(route) or not np.isfinite(np.asarray(heights, float)).all():
            raise ValueError("Ответ сервиса высот содержит пропуски или неверные значения")
        result = route.copy()
        result["elevation_raw_m"] = heights
        # Trailing smoothing is causal: future elevations cannot leak into ML inputs.
        result["elevation_m"] = pd.Series(heights).rolling(3, min_periods=1).mean().to_numpy()
        result["is_restored"] = 0
        return cls.slopes(result)

    @staticmethod
    def validate(route: pd.DataFrame) -> pd.DataFrame:
        required = ["point_id", "latitude", "longitude", "segment_distance_m",
                    "total_distance_m", "elevation_m", "slope_pct"]
        if len(route) < 2 or not set(required).issubset(route.columns):
            raise ValueError("CSV пуст или не содержит обязательные столбцы маршрута")
        result = route.copy()
        result[required] = result[required].apply(pd.to_numeric, errors="raise")
        if not np.isfinite(result[required].to_numpy()).all():
            raise ValueError("CSV содержит пропуски или бесконечные значения")
        d = result.total_distance_m.to_numpy()
        if abs(d[0]) > 1e-5 or (np.diff(d) <= 0).any():
            raise ValueError("Расстояние должно строго возрастать от нуля")
        if not np.allclose(result.segment_distance_m, np.r_[0, np.diff(d)], atol=0.01):
            raise ValueError("Длины отрезков не совпадают с накопленным расстоянием")
        if (result.latitude.abs() > 90).any() or (result.longitude.abs() > 180).any():
            raise ValueError("Некорректные координаты маршрута")
        return result.reset_index(drop=True)

    @classmethod
    def load(cls, path: Path) -> pd.DataFrame:
        return cls.validate(pd.read_csv(path))

    @staticmethod
    def save(route: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        route.to_csv(temporary, index=False, encoding="utf-8", float_format="%.8f")
        temporary.replace(path)

    @staticmethod
    def position(route: pd.DataFrame, distance_m: float) -> RoutePoint:
        d = route.total_distance_m.to_numpy()
        values = [float(np.interp(distance_m, d, route[c]))
                  for c in ("latitude", "longitude", "elevation_m", "slope_pct")]
        return RoutePoint(*values, float(np.clip(distance_m, 0, d[-1])))
