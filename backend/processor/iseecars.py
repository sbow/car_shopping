"""iSeeCars.com cross-sectional market price scraper.

Fetches the "Average price by year" chart data embedded in each model's
listing page as a JS array literal, e.g.:

    var dataRows = [
        [18046,2019],
        [17401,2018],
        ...
    ];
"""

import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.iseecars.com/used_cars-t5989-used-{make}-{model}-for-sale"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_DATAROWS_RE = re.compile(
    r"var dataRows = \[(.*?)\];\s*iseecars\.chart\.dyk\.drawPriceByYear", re.S
)
_PAIR_RE = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-")


def fetch_and_store(make: str, model: str, session) -> int:
    """Fetch iSeeCars year-by-year prices and upsert into market_price_snapshots.

    Returns the number of rows upserted. Returns 0 (without raising) on any
    fetch or parse failure.
    """
    from sqlalchemy.dialects.postgresql import insert
    from backend.models import MarketPriceSnapshot

    url = _BASE_URL.format(make=_slug(make), model=_slug(model))
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
    except Exception:
        logger.warning("iSeeCars fetch failed for %s %s", make, model)
        return 0

    m = _DATAROWS_RE.search(r.text)
    if not m:
        logger.warning("iSeeCars price-by-year table not found for %s %s", make, model)
        return 0

    pairs = _PAIR_RE.findall(m.group(1))
    if not pairs:
        return 0

    count = 0
    for price_str, year_str in pairs:
        price, year = float(price_str), int(year_str)
        stmt = (
            insert(MarketPriceSnapshot)
            .values(make=make, model=model, year=year, median_price=price, source="iseecars")
            .on_conflict_do_update(
                index_elements=["make", "model", "year", "source"],
                set_={"median_price": price},
            )
        )
        session.execute(stmt)
        count += 1

    time.sleep(2)
    return count
