"""EPA fueleconomy.gov API client with local JSON cache."""

import json
import logging
import os
import requests

logger = logging.getLogger(__name__)

_CACHE_PATH = os.path.join(os.path.dirname(__file__), "mpg_cache.json")
_BASE_URL = "https://www.fueleconomy.gov/ws/rest"
_HEADERS = {"Accept": "application/json"}

_cache: dict = {}
_cache_loaded = False


def _load_cache() -> None:
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH) as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    _cache_loaded = True


def _save_cache() -> None:
    with open(_CACHE_PATH, "w") as f:
        json.dump(_cache, f, indent=2)


def get_mpg(make: str, model: str, year: int) -> float | None:
    """Return combined MPG or blended MPGe for make/model/year.

    PHEVs (e.g. Volt) use phevComb; gas/hybrid vehicles use comb08.
    Caches results in mpg_cache.json. Returns None if EPA has no data.
    """
    _load_cache()
    key = f"{make}|{model}|{year}"
    if key in _cache:
        return _cache[key]

    try:
        r = requests.get(
            f"{_BASE_URL}/vehicle/menu/options",
            params={"year": year, "make": make, "model": model},
            headers=_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        items = r.json().get("menuItem", [])
    except Exception:
        logger.warning("EPA API unavailable for %s %s %s", year, make, model)
        _cache[key] = None
        _save_cache()
        return None

    if isinstance(items, dict):
        items = [items]

    vehicle_ids = [item["value"] for item in items if "value" in item]
    if not vehicle_ids:
        logger.warning("No EPA vehicle IDs found for %s %s %s", year, make, model)
        _cache[key] = None
        _save_cache()
        return None

    mpg_values: list[float] = []
    for vid in vehicle_ids:
        try:
            vr = requests.get(f"{_BASE_URL}/vehicle/{vid}", headers=_HEADERS, timeout=10)
            vr.raise_for_status()
            v = vr.json()
            # EPA returns "0" (string) for phevComb on non-PHEVs — must compare numerically
            phev = float(v.get("phevComb") or 0)
            comb = float(v.get("comb08") or 0)
            val = phev if phev > 0 else (comb if comb > 0 else None)
            if val:
                mpg_values.append(val)
        except Exception:
            logger.warning("Failed to fetch EPA data for vehicle ID %s", vid)

    result = round(sum(mpg_values) / len(mpg_values), 1) if mpg_values else None
    _cache[key] = result
    _save_cache()
    return result
