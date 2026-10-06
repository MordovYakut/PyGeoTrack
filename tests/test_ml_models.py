import numpy as np
import pytest
from models.terrain_restorer import TerrainRestorer, create_missing
from models.slope_predictor import SlopePredictor


def test_restoration_and_known_values(route):
    missing = create_missing(route)
    mask = missing.elevation_m.isna()
    assert mask.sum() == round(len(route) * .2)
    assert not mask.iloc[0] and not mask.iloc[-1]
    assert any(mask.iloc[i:i + 3].all() for i in range(len(mask) - 2))
    assert missing.loc[mask, "elevation_raw_m"].isna().all()
    restorer = TerrainRestorer()
    restored = restorer.restore(missing)
    assert np.isfinite(restored.elevation_m).all()
    assert np.allclose(restored.loc[~mask, "elevation_m"], route.loc[~mask, "elevation_m"])
    assert restored.is_restored.sum() == mask.sum()
    assert restorer.metrics["mae_m"] >= 0
    assert hasattr(restorer.model, "estimators_")


def test_slope_predictions_and_purging(route):
    model = SlopePredictor()
    model.fit(route)
    pred = model.predict(route)
    assert model.ready
    assert len(pred) == len(route)
    assert np.isfinite(pred).all()
    assert model.metrics["train_label_end_m"] < model.metrics["validation_start_m"] - 200


def test_causal_features(route):
    first = SlopePredictor.features(route)
    changed = route.copy()
    changed.loc[100:, "elevation_m"] += 1000
    changed.loc[100:, "slope_pct"] += 50
    assert np.array_equal(first[:100], SlopePredictor.features(changed)[:100])


def test_small_route_and_all_missing(route):
    short = route.iloc[:3].copy()
    model = SlopePredictor()
    model.fit(short)
    assert np.isfinite(model.predict(short)).all()
    short["elevation_m"] = np.nan
    with pytest.raises(ValueError):
        TerrainRestorer().restore(short)
