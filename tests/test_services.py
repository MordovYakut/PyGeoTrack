from unittest.mock import Mock
import numpy as np
import pytest
import requests
from config import settings as cfg
from services.route_service import RouteService
from services.elevation_service import ElevationService
from services.pipeline import RoutePipeline


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr("services.http_client.time.sleep", lambda _: None)


def test_osrm_parameters(monkeypatch):
    response = Mock()
    response.json.return_value = {"code": "Ok", "routes": [{"distance": 100, "duration": 10,
        "geometry": {"type": "LineString", "coordinates": [[11, 47], [11.01, 47.01]]}}]}
    get = Mock(return_value=response)
    monkeypatch.setattr("services.http_client.requests.get", get)
    result = RouteService().fetch((47, 11), (47.01, 11.01))
    assert result.distance_m == 100
    assert "/driving/11,47;11.01,47.01" in get.call_args.args[0]
    assert get.call_args.kwargs["params"]["overview"] == "full"


@pytest.mark.parametrize("failure", [requests.Timeout(), ValueError("bad JSON"), requests.HTTPError("503")])
def test_retries(monkeypatch, failure):
    get = Mock(side_effect=failure)
    monkeypatch.setattr("services.http_client.requests.get", get)
    with pytest.raises(RuntimeError):
        RouteService().fetch((47, 11), (48, 12))
    assert get.call_count == cfg.HTTP_ATTEMPTS


def test_elevation_batching(monkeypatch, route):
    batches = []
    def get(url, params, **kwargs):
        count = len(params["latitude"].split(","))
        batches.append(count)
        return Mock(json=lambda: {"elevation": [100] * count})
    monkeypatch.setattr("services.http_client.requests.get", get)
    heights = ElevationService().fetch(route)
    assert len(heights) == len(route)
    assert max(batches) <= 100
    assert len(batches) == int(np.ceil(len(route) / 100))


@pytest.mark.parametrize("payload", [[], {}, {"code": "NoRoute"}, {"code": "Ok", "routes": []}])
def test_bad_osrm_json(monkeypatch, payload):
    get = Mock(return_value=Mock(json=lambda: payload))
    monkeypatch.setattr("services.http_client.requests.get", get)
    with pytest.raises(RuntimeError):
        RouteService().fetch((47, 11), (48, 12))
    assert get.call_count == cfg.HTTP_ATTEMPTS


@pytest.mark.parametrize("payload", [[], {}, {"elevation": [None]}, {"elevation": []}])
def test_bad_elevation_json(monkeypatch, route, payload):
    get = Mock(return_value=Mock(json=lambda: payload))
    monkeypatch.setattr("services.http_client.requests.get", get)
    with pytest.raises(RuntimeError):
        ElevationService().fetch(route.iloc[:1])
    assert get.call_count == cfg.HTTP_ATTEMPTS


def test_offline_fallback_with_corrupt_cache(monkeypatch, tmp_path):
    (tmp_path / "route_original.csv").write_text("bad CSV")
    monkeypatch.setattr("services.route_service.RouteService.fetch", Mock(side_effect=RuntimeError("offline")))
    bundle = RoutePipeline(tmp_path).load(force_network=True)
    assert "API недоступен" in bundle.status
    assert len(bundle.route) > 100
    assert np.isfinite(bundle.route.elevation_m).all()
    assert bundle.original.elevation_m.isna().sum() == 0
    assert bundle.original is not bundle.route


def test_elevation_batches_cached(monkeypatch, route, tmp_path):
    def get(url, params, **kwargs):
        return Mock(json=lambda: {"elevation": [123] * len(params["latitude"].split(","))})
    fetch = Mock(side_effect=get)
    monkeypatch.setattr("services.http_client.requests.get", fetch)
    first = ElevationService().fetch(route, tmp_path)
    calls = fetch.call_count
    assert ElevationService().fetch(route, tmp_path) == first
    assert fetch.call_count == calls
