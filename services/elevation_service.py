import logging
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from config import settings as cfg
from services.http_client import get_json


class ElevationService:
    def fetch(self, points: pd.DataFrame, cache_dir: Path | None = None) -> list[float]:
        heights = []
        requested = False
        for start in range(0, len(points), cfg.ELEVATION_BATCH_SIZE):
            batch = points.iloc[start:start + cfg.ELEVATION_BATCH_SIZE]

            def validate(data):
                if not isinstance(data, dict):
                    raise ValueError("Сервис высот должен вернуть объект JSON")
                values = np.asarray(data["elevation"], dtype=float)
                if values.shape != (len(batch),) or not np.isfinite(values).all():
                    raise ValueError("Некорректный пакет высот")
                return values.tolist()

            params = {
                "latitude": ",".join(f"{v:.6f}" for v in batch.latitude),
                "longitude": ",".join(f"{v:.6f}" for v in batch.longitude),
            }
            cache_path = None
            if cache_dir is not None:
                key = hashlib.sha256((cfg.ELEVATION_API_URL + json.dumps(params, sort_keys=True)).encode()).hexdigest()
                cache_path = cache_dir / f"{key}.json"
                try:
                    heights.extend(validate(json.loads(cache_path.read_text(encoding="utf-8"))))
                    continue
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            # A long route can exhaust the public service's per-minute quota.
            if requested:
                time.sleep(cfg.ELEVATION_BATCH_INTERVAL_S)
            values = get_json(cfg.ELEVATION_API_URL, params, validate)
            requested = True
            heights.extend(values)
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps({"elevation": values}), encoding="utf-8")
            logging.getLogger(__name__).info("Высоты: %d из %d точек", len(heights), len(points))
        logging.getLogger(__name__).info("Elevation: %d points", len(heights))
        return heights
