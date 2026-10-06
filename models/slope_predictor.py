"""Causal route features and a purged chronological validation split."""
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from config import settings as cfg


class SlopePredictor:
    def __init__(self, horizon_m: float = cfg.PREDICTION_DISTANCE_M):
        self.horizon_m = horizon_m
        self.model = RandomForestRegressor(n_estimators=100, min_samples_leaf=2,
                                           random_state=cfg.RANDOM_SEED, n_jobs=1)
        self.metrics: dict = {}
        self.ready = False

    @staticmethod
    def features(route: pd.DataFrame) -> np.ndarray:
        slope = route.slope_pct
        # Absolute coordinates/elevation mostly memorize the route and extrapolate badly.
        # Local gradients and relative elevation history transfer between route sections.
        features = route[["slope_pct"]].copy()
        for lag in (1, 2, 3):
            features[f"slope_lag_{lag}"] = slope.shift(lag).fillna(slope.iloc[0])
        for lag in (1, 3, 6):
            features[f"elevation_delta_{lag}"] = route.elevation_m - route.elevation_m.shift(lag).fillna(route.elevation_m.iloc[0])
        features["slope_mean"] = slope.rolling(4, min_periods=1).mean()
        features["slope_std"] = slope.rolling(4, min_periods=1).std().fillna(0)
        return features.to_numpy(float)

    def fit(self, route: pd.DataFrame) -> None:
        distance = route.total_distance_m.to_numpy()
        x_all = self.features(route)
        valid = np.flatnonzero(distance + self.horizon_m <= distance[-1])
        if len(valid) < 8:
            self.metrics = {"note": "Маршрут слишком короткий; используется текущий уклон", "validation_points": 0}
            return
        x = x_all[valid]
        y = np.interp(distance[valid] + self.horizon_m, distance, route.slope_pct)
        cut = int(len(valid) * 0.75)
        # Purge labels that reach the validation segment, plus three causal lags.
        boundary = distance[valid[max(0, cut - 3)]]
        train = np.flatnonzero(distance[valid] + self.horizon_m < boundary)
        test = np.arange(cut, len(valid))
        if len(train) >= 8 and len(test) >= 2:
            self.model.fit(x[train], y[train])
            prediction = self.model.predict(x[test])
            self.metrics = {
                "mae_pct": float(mean_absolute_error(y[test], prediction)),
                "rmse_pct": float(np.sqrt(mean_squared_error(y[test], prediction))),
                "r2": float(r2_score(y[test], prediction)) if np.var(y[test]) > 1e-12 else None,
                "validation_points": len(test), "train_points": len(train),
                "train_label_end_m": float((distance[valid[train]] + self.horizon_m).max()),
                "validation_start_m": float(distance[valid[cut]]),
                "persistence_mae_pct": float(mean_absolute_error(y[test], route.slope_pct.to_numpy()[valid[test]])),
            }
        else:
            self.metrics = {"validation_points": 0, "note": "Недостаточно точек для проверки"}
        # Production is route-specific: after honest evaluation, use all valid route pairs.
        self.model.fit(x, y)
        self.ready = True
        logging.getLogger(__name__).info("Прогноз уклона (%g м): %s", self.horizon_m, self.metrics)

    def predict(self, route: pd.DataFrame) -> np.ndarray:
        if not self.ready:
            return route.slope_pct.to_numpy().copy()
        return np.clip(self.model.predict(self.features(route)), -cfg.MAX_SLOPE_PCT, cfg.MAX_SLOPE_PCT)
