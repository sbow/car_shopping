"""Estimate $/yr depreciation for vehicles of interest.

Heuristic: for a target year T, find median listing price for the same
make/model at T-5 and T-10, then compute:
  rate_5yr  = (median_price_T - median_price_T5)  / 5
  rate_10yr = (median_price_T - median_price_T10) / 10
"""

import logging
import statistics
from sqlalchemy import select, func
from backend.models import Listing, DepreciationEstimate, MarketPriceSnapshot
from backend.processor import iseecars
import backend.db as db
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def compute_all(cfg: dict) -> None:
    session = db.get_session()
    try:
        for v in cfg.get("vehicles", []):
            make, model = v["make"], v["model"]

            iseecars.fetch_and_store(make, model, session)

            # Use the most recent year with actual listings rather than year_max from
            # config, which is often a future year with no data.
            base_year = session.execute(
                select(func.max(Listing.year))
                .where(Listing.make == make, Listing.model == model)
                .where(Listing.price.isnot(None))
            ).scalar()
            if not base_year:
                continue
            estimate = _compute(session, make, model, base_year)
            if estimate:
                _upsert(session, estimate)

            exp_estimate = _exponential_estimate(session, make, model, base_year)
            if exp_estimate:
                _upsert(session, exp_estimate)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Depreciation computation failed")
        raise
    finally:
        session.close()


def _estimate_r(v0: float, vt: float, t: int) -> float | None:
    """Estimate annual decay rate r from V(t) = V0*(1-r)^t.

    Returns None if inputs are invalid or the result falls outside a
    plausible range for used-car depreciation.
    """
    if t < 2 or v0 <= 0 or vt <= 0 or vt >= v0:
        return None
    r = 1 - (vt / v0) ** (1 / t)
    return r if 0.01 <= r <= 0.50 else None


def _exponential_estimate(session, make: str, model: str, base_year: int) -> dict | None:
    """Estimate depreciation via V(t) = V0*(1-r)^t.

    V0 is the median price of our own scraped listings at base_year (the price
    the user would actually pay). V(t) candidates come from cross-sectional
    market prices (iSeeCars) merged with our own listings at other years.
    """
    v0 = _median_price(session, make, model, base_year)
    if v0 is None:
        return None

    prices: dict[int, float] = {}

    listing_rows = session.execute(
        select(Listing.year, Listing.price)
        .where(Listing.make == make, Listing.model == model, Listing.year != base_year)
        .where(Listing.price.isnot(None))
    ).all()
    by_year: dict[int, list[float]] = {}
    for year, price in listing_rows:
        by_year.setdefault(year, []).append(price)
    for year, values in by_year.items():
        prices[year] = statistics.median(values)

    snapshot_rows = session.execute(
        select(MarketPriceSnapshot.year, MarketPriceSnapshot.median_price)
        .where(MarketPriceSnapshot.make == make, MarketPriceSnapshot.model == model)
        .where(MarketPriceSnapshot.year != base_year)
    ).all()
    for year, price in snapshot_rows:
        prices[int(year)] = float(price)  # iSeeCars takes precedence per year

    r_values = []
    for year, price in prices.items():
        t = base_year - year
        r = _estimate_r(v0, price, t)
        if r is not None:
            r_values.append(r)

    if not r_values:
        return None

    return {
        "make": make,
        "model": model,
        "base_year": base_year,
        "rate_r": round(statistics.median(r_values), 4),
    }


def _median_price(session, make: str, model: str, year: int) -> float | None:
    rows = session.execute(
        select(Listing.price)
        .where(Listing.make == make, Listing.model == model, Listing.year == year)
        .where(Listing.price.isnot(None))
    ).scalars().all()
    if not rows:
        return None
    return statistics.median(rows)


def _compute(session, make: str, model: str, base_year: int) -> dict | None:
    p_base = _median_price(session, make, model, base_year)
    if p_base is None:
        logger.info("No listings for %s %s %d", make, model, base_year)
        return None

    rate_5yr = rate_10yr = None

    p5 = _median_price(session, make, model, base_year - 5)
    if p5 is not None:
        rate_5yr = (p_base - p5) / 5
        logger.info("%s %s: rate_5yr = $%.0f/yr (base %d vs %d)", make, model, rate_5yr, base_year, base_year - 5)

    p10 = _median_price(session, make, model, base_year - 10)
    if p10 is not None:
        rate_10yr = (p_base - p10) / 10
        logger.info("%s %s: rate_10yr = $%.0f/yr (base %d vs %d)", make, model, rate_10yr, base_year, base_year - 10)

    return {"make": make, "model": model, "base_year": base_year,
            "rate_5yr": rate_5yr, "rate_10yr": rate_10yr}


def _upsert(session, est: dict) -> None:
    from sqlalchemy.dialects.postgresql import insert
    rate_fields = {k: v for k, v in est.items() if k not in ("make", "model", "base_year")}
    stmt = (
        insert(DepreciationEstimate)
        .values(**est, computed_at=datetime.now(timezone.utc))
        .on_conflict_do_update(
            index_elements=["make", "model", "base_year"],
            set_={**rate_fields, "computed_at": datetime.now(timezone.utc)},
        )
    )
    session.execute(stmt)
