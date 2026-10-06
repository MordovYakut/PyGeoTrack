"""Supervised elevation reconstruction; no target interpolation."""
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from config import settings as cfg
from services.route_processor import RouteProcessor


def create_missing(route: pd.DataFrame, fraction: float = cfg.MISSING_ELEVATION_FRACTION) -> pd.DataFrame:
    if not 0 < fraction < 0.5:
        raise ValueError("Доля пропусков должна быть между 0 и 0,5")
    result = route.copy()
    count = min(round(len(result) * fraction), max(0, len(result) - 2))
    rng = np.random.default_rng(cfg.RANDOM_SEED)
    mask = np.zeros(len(result), dtype=bool)
    if count:
        # Exact requested count (rounded to one row), with separated contiguous blocks.
        # Distribute spare rows among gaps instead of repeatedly overlapping random blocks.
        block_count = max(1, int(np.ceil(count / 6)))
        lengths = np.full(block_count, count // block_count, dtype=int)
        lengths[:count % block_count] += 1
        rng.shuffle(lengths)
        spare = len(result) - 2 - count - (block_count - 1)
        gaps = rng.multinomial(spare, np.full(block_count + 1, 1 / (block_count + 1)))
        position = 1 + gaps[0]
        for index, length in enumerate(lengths):
            mask[position:position + length] = True
            position += length + 1 + gaps[index + 1]
    # Remove raw targets too: they must not expose the deliberately hidden values.
    result.loc[mask, "elevation_m"] = np.nan
    if "elevation_raw_m" in result:
        result.loc[mask, "elevation_raw_m"] = np.nan
    result["is_restored"] = 0
    return RouteProcessor.slopes(result)


class TerrainRestorer:
    features = ["latitude", "longitude", "total_distance_m"]

    def __init__(self):
        self.model = ExtraTreesRegressor(n_estimators=120, min_samples_leaf=1,
                                         random_state=cfg.RANDOM_SEED, n_jobs=1)
        self.metrics: dict = {}

    def restore(self, route: pd.DataFrame) -> pd.DataFrame:
        result = route.copy()
        known = np.flatnonzero(np.isfinite(result.elevation_m.to_numpy()))
        missing = ~np.isfinite(result.elevation_m.to_numpy())
        if not len(known):
            raise ValueError("Для восстановления нужна хотя бы одна известная высота")
        x = result[self.features].to_numpy(float)
        y = result.elevation_m.to_numpy(float)
        if not np.isfinite(x).all():
            raise ValueError("В признаках рельефа есть пропуски")
        if len(known) >= 20:
            # Hold out contiguous blocks of known rows, not isolated random samples.
            held = np.concatenate([known[k:k + 4] for k in range(8, len(known) - 4, 25)])
            train = np.setdiff1d(known, held)
            self.model.fit(x[train], y[train])
            pred = self.model.predict(x[held])
            self.metrics = {"mae_m": float(mean_absolute_error(y[held], pred)),
                            "rmse_m": float(np.sqrt(mean_squared_error(y[held], pred))),
                            "validation_points": len(held)}
        else:
            self.metrics = {"validation_points": 0, "note": "Недостаточно точек для проверки"}
        self.model.fit(x[known], y[known])
        if missing.any():
            result.loc[missing, "elevation_m"] = self.model.predict(x[missing])
        result["is_restored"] = missing.astype(int)
        self.metrics["restored_points"] = int(missing.sum())
        logging.getLogger(__name__).info("Восстановление рельефа: %s", self.metrics)
        return RouteProcessor.slopes(result)
