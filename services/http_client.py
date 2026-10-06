"""Bounded retries covering HTTP, timeout and malformed JSON failures."""
import logging
import time
from typing import Any, Callable
import requests
from config import settings as cfg

log = logging.getLogger(__name__)


def get_json(url: str, params: dict, validate: Callable[[Any], Any]) -> Any:
    last_error = None
    for attempt in range(cfg.HTTP_ATTEMPTS):
        try:
            response = requests.get(url, params=params, timeout=cfg.HTTP_TIMEOUT_S,
                                    headers={"User-Agent": "PyGeoTrack/1.0 educational desktop"})
            response.raise_for_status()
            return validate(response.json())
        except (requests.RequestException, ValueError, TypeError, KeyError, IndexError) as exc:
            last_error = exc
            log.warning("Попытка API %d/%d: %s", attempt + 1, cfg.HTTP_ATTEMPTS, str(exc)[:250])
            if attempt + 1 < cfg.HTTP_ATTEMPTS:
                delay = 0.5 * (attempt + 1)
                if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code == 429:
                    try:
                        delay = min(60.0, max(15.0, float(exc.response.headers.get("Retry-After", 60))))
                    except (ValueError, TypeError):
                        delay = 60.0
                time.sleep(delay)
    raise RuntimeError(f"API недоступен: {url}. Проверьте подключение или повторите позже.") from last_error
