import numpy as np
import pandas as pd
import pytest
from services.route_processor import RouteProcessor as RP, haversine


def test_haversine():
    assert haversine(0, 0, 0, 1) == pytest.approx(111195.08, rel=1e-5)
    assert haversine(47, 11, 47, 11) == 0


def test_resampling_and_endpoint():
    geometry = [[11, 47], [11, 47], [11.002, 47], [11.005, 47.002]]
    p = RP.resample(geometry)
    assert np.all(np.diff(p.total_distance_m) > 0)
    assert np.allclose(p.segment_distance_m.iloc[1:-1], 100)
    assert p.iloc[-1].latitude == 47.002
    assert p.iloc[-1].longitude == pytest.approx(11.005)
    assert p.segment_distance_m.iloc[-1] <= 100


def test_slopes_and_zero_distance():
    p = pd.DataFrame({"elevation_m": [10, 12, 13], "segment_distance_m": [0, 100, 0]})
    out = RP.slopes(p)
    assert out.slope_pct.iloc[0] == 0
    assert out.slope_pct.iloc[1] == 2
    assert np.isnan(out.slope_pct.iloc[2])


def test_empty_nan_bad_distance(route, tmp_path):
    with pytest.raises(ValueError):
        RP.validate(pd.DataFrame())
    route.loc[1, "elevation_m"] = np.nan
    with pytest.raises(ValueError):
        RP.validate(route)
    (tmp_path / "empty.csv").write_text("")
    with pytest.raises(ValueError):
        RP.load(tmp_path / "empty.csv")


def test_csv_roundtrip(route, tmp_path):
    RP.save(route, tmp_path / "route.csv")
    restored = RP.load(tmp_path / "route.csv")
    assert np.allclose(restored.elevation_m, route.elevation_m)


@pytest.mark.parametrize("geometry", [[], [[1, 2]], [[1, 2], [1, 2]], [[181, 2], [1, 2]]])
def test_invalid_geometry(geometry):
    with pytest.raises(ValueError):
        RP.resample(geometry)
