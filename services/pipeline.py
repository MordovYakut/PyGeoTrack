"""Load/cache/network orchestration. Called exclusively by a background worker."""
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from config import settings as cfg
from services.route_service import RouteService
from services.elevation_service import ElevationService
from services.route_processor import RouteProcessor as RP
from models.terrain_restorer import TerrainRestorer, create_missing
from models.slope_predictor import SlopePredictor

log = logging.getLogger(__name__)


@dataclass
class RouteBundle:
    route: pd.DataFrame
    geometry: list
    metadata: dict
    metrics: dict
    status: str
    original: pd.DataFrame


class RoutePipeline:
    def __init__(self, data_dir: Path = cfg.DATA_DIR):
        self.data_dir = data_dir

    def _cached(self, folder: Path) -> tuple[pd.DataFrame, list, dict]:
        route = RP.load(folder / "route_original.csv")
        metadata = {"name": "Локальный маршрут", "source": "Локальные данные CSV"}
        try:
            metadata.update(json.loads((folder / "route_metadata.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            pass
        geometry = route[["longitude", "latitude"]].values.tolist()
        try:
            candidate = json.loads((folder / "route_geometry.geojson").read_text(encoding="utf-8"))["coordinates"]
            check = RP.resample(candidate)
            endpoints = np.asarray(candidate)[[0, -1]]
            if (np.allclose(endpoints, np.asarray(geometry)[[0, -1]], atol=1e-5)
                    and abs(check.total_distance_m.iloc[-1] - route.total_distance_m.iloc[-1]) < 1):
                geometry = candidate
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            log.warning("Полная геометрия недоступна; используются точки профиля")
        return route, geometry, metadata

    def load(self, start: tuple[float, float] = (cfg.START_LAT, cfg.START_LON),
             end: tuple[float, float] = (cfg.END_LAT, cfg.END_LON),
             force_network: bool = False) -> RouteBundle:
        loaded = None
        status = "Используются локальные данные маршрута"
        if cfg.USE_CACHED_ROUTE and not force_network:
            try:
                loaded = self._cached(self.data_dir)
            except (OSError, ValueError, pd.errors.ParserError):
                log.warning("Основной сохранённый маршрут недоступен")
        if loaded is None:
            try:
                road = RouteService().fetch(start, end)
                samples = RP.resample(road.coordinates)
                route = RP.with_elevation(samples, ElevationService().fetch(
                    samples, cache_dir=self.data_dir / "elevation_cache"))
                name = cfg.DEFAULT_ROUTE_NAME if start == (cfg.START_LAT, cfg.START_LON) and end == (cfg.END_LAT, cfg.END_LON) else "Пользовательский маршрут"
                metadata = {"name": name, "start": start, "end": end,
                            "distance_m": road.distance_m, "duration_s": road.duration_s,
                            "source": "OSRM / OpenStreetMap; Open-Meteo / Copernicus DEM GLO-90"}
                loaded = route, road.coordinates, metadata
                self.data_dir.mkdir(parents=True, exist_ok=True)
                RP.save(route, self.data_dir / "route_original.csv")
                (self.data_dir / "route_geometry.geojson").write_text(json.dumps(road.geojson), encoding="utf-8")
                (self.data_dir / "route_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
                status = "Маршрут OSRM построен · Высоты загружены"
            except (RuntimeError, OSError, ValueError) as exc:
                log.warning("Ошибка сетевой загрузки; загружаются локальные данные: %s", exc)
                for folder in (self.data_dir, cfg.DATA_DIR / "demo"):
                    try:
                        loaded = self._cached(folder)
                        status = "API недоступен · Локальный маршрут: " + loaded[2]["name"]
                        break
                    except (OSError, ValueError, pd.errors.ParserError):
                        continue
        if loaded is None:
            raise RuntimeError("Локальный маршрут повреждён, API недоступен. Восстановите data/demo или повторите запрос при подключении к сети.")
        original, geometry, metadata = loaded
        missing = create_missing(original)
        terrain = TerrainRestorer()
        restored = terrain.restore(missing)
        slope = SlopePredictor()
        slope.fit(original)
        restored["predicted_slope_pct"] = slope.predict(restored)
        restored["prediction_available"] = (restored.total_distance_m + cfg.PREDICTION_DISTANCE_M <= restored.total_distance_m.iloc[-1]).astype(int)
        metrics = {"terrain": terrain.metrics, "slope": slope.metrics, "slope_ready": slope.ready}
        RP.validate(restored)
        try:
            for name, frame in (("route_missing", missing), ("route_restored", restored), ("route", restored)):
                RP.save(frame, self.data_dir / f"{name}.csv")
            (self.data_dir / "ml_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        except OSError as exc:
            log.warning("Не удалось сохранить обработанные данные: %s", exc)
            status += " · Не удалось сохранить CSV"
        return RouteBundle(restored, geometry, metadata, metrics, status, original.copy())
