"""CarGurus make/model entity ID registry.

CarGurus routes search pages by numeric entity IDs:
  Make:  https://www.cargurus.com/Cars/l-Used-Cadillac-m22
  Model: https://www.cargurus.com/Cars/l-Used-Cadillac-XTS-d2141

IDs are discovered by loading make pages and parsing the filter facet JSON
embedded in the page (``"name":"m1/d2012","label":"Volt"``).

Run as a script to refresh the on-disk cache:
  python -m backend.scraper.cargurus_ids
"""

import re
import json
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

_CACHE = Path(__file__).parent / "cargurus_ids.json"
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# Discovered make entity IDs
_MAKE_IDS: dict[str, str] = {
    "chevrolet": "m1",
    "ford": "m2",
    "bmw": "m3",
    "acura": "m4",
    "honda": "m6",
    "toyota": "m7",
    "nissan": "m12",
    "buick": "m21",
    "cadillac": "m22",
    "chrysler": "m23",
    "dodge": "m24",
    "gmc": "m26",
    "hyundai": "m28",
    "jaguar": "m31",
    "kia": "m33",
}

# Pre-seeded model entity IDs (verified against live pages)
_SEED: dict[str, dict[str, str]] = {
    "Cadillac XTS":   {"makeId": "m22", "modelId": "d2141"},
    "Cadillac CT6":   {"makeId": "m22", "modelId": "d2352"},
    "Chevrolet Volt": {"makeId": "m1",  "modelId": "d2012"},
}


def load_cache() -> dict:
    if _CACHE.exists():
        return json.loads(_CACHE.read_text())
    # Bootstrap with seed data so the first run doesn't need discovery
    cache = dict(_SEED)
    _save_cache(cache)
    return cache


def _save_cache(cache: dict) -> None:
    _CACHE.write_text(json.dumps(cache, indent=2))


def get_entity_ids(make: str, model: str) -> tuple[str | None, str | None]:
    """Return (makeId, modelId) strings (e.g. 'm22', 'd2141') for a vehicle."""
    cache = load_cache()
    key = f"{make} {model}"
    if key in cache:
        entry = cache[key]
        return entry.get("makeId"), entry.get("modelId")

    logger.info("Discovering CarGurus IDs for %s %s", make, model)
    make_id = _MAKE_IDS.get(make.lower())
    if not make_id:
        logger.warning("No known makeId for '%s'", make)
        return None, None

    model_id = _discover_model_id(make, make_id, model)
    if model_id:
        cache[key] = {"makeId": make_id, "modelId": model_id}
        _save_cache(cache)
        logger.info("Cached: %s -> makeId=%s modelId=%s", key, make_id, model_id)
    return make_id, model_id


def _discover_model_id(make: str, make_id: str, model: str) -> str | None:
    """Load the make page and parse model IDs from the filter facet JSON."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        try:
            url = f"https://www.cargurus.com/Cars/l-Used-{make}-{make_id}"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)
            html = page.content()
            # Facet format: {"name":"m1/d2012","label":"Volt",...}
            pattern = rf'"name":"{re.escape(make_id)}/(d\d+)","label":"([^"]+)"'
            for m in re.finditer(pattern, html):
                model_id, label = m.group(1), m.group(2)
                if label.lower() == model.lower():
                    return model_id
            logger.warning("modelId not found for '%s' on %s make page", model, make)
        except Exception:
            logger.exception("Discovery error for %s %s", make, model)
        finally:
            browser.close()
    return None


def build_search_url(make: str, model: str, make_id: str, model_id: str,
                     zip_code: str, radius: int, year_min: int, year_max: int,
                     min_price: int | None, max_price: int | None,
                     max_mileage: int | None) -> str:
    """Return a CarGurus search URL with entity-ID routing and filter params."""
    make_slug = make.replace(" ", "-")
    model_slug = model.replace(" ", "-")
    base = (
        f"https://www.cargurus.com/Cars/l-Used-{make_slug}-{model_slug}-{model_id}"
    )
    params: dict[str, str | int] = {
        "zip": zip_code,
        "distance": radius,
        "startYear": year_min,
        "endYear": year_max,
        "sortDir": "ASC",
        "sortType": "PRICE",
    }
    if min_price:
        params["minPrice"] = min_price
    if max_price:
        params["maxPrice"] = max_price
    if max_mileage:
        params["maxMileage"] = max_mileage
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{qs}"


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.path.insert(0, str(Path(__file__).parents[3]))

    vehicles = [
        ("Cadillac", "XTS"),
        ("Cadillac", "CT6"),
        ("Chevrolet", "Volt"),
    ]
    for make, model in vehicles:
        mid, vid = get_entity_ids(make, model)
        print(f"{make} {model}: makeId={mid} modelId={vid}")
