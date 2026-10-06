from dataclasses import dataclass
import logging
import math
from config import settings as cfg
from services.http_client import get_json
from services.route_processor import RouteProcessor


@dataclass
class RoadRoute:
    coordinates: list
    distance_m: float
    duration_s: float
    geojson: dict


class RouteService:
    def fetch(self, start: tuple[float, float], end: tuple[float, float]) -> RoadRoute:
        """Input tuples are (latitude, longitude); OSRM expects longitude first."""
        for lat, lon in (start, end):
            if not math.isfinite(lat + lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("Некорректные координаты начала или конца маршрута")
        url = f"{cfg.OSRM_BASE_URL}/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}"

        def validate(data):
            if not isinstance(data, dict):
                raise ValueError("OSRM должен вернуть объект JSON")
            if data.get("code") != "Ok":
                raise ValueError(data.get("message", "OSRM не нашёл маршрут"))
            route = data["routes"][0]
            geometry = route["geometry"]
            if geometry["type"] != "LineString":
                raise ValueError("Ожидалась дорожная линия LineString")
            RouteProcessor.resample(geometry["coordinates"])
            distance, duration = float(route["distance"]), float(route["duration"])
            if not math.isfinite(distance + duration) or distance <= 0 or duration < 0:
                raise ValueError("Некорректная длина или длительность маршрута")
            return RoadRoute(geometry["coordinates"], distance, duration, geometry)

        result = get_json(url, {"geometries": "geojson", "overview": "full", "steps": "false"}, validate)
        logging.getLogger(__name__).info("OSRM: %.2f km", result.distance_m / 1000)
        return result
