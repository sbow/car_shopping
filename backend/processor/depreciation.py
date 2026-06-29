"""Estimate $/yr depreciation for vehicles of interest.

Heuristic: for a target year T, find median listing price for the same
make/model at T-5 and T-10, then compute:
  rate_5yr  = (median_price_T - median_price_T5)  / 5
  rate_10yr = (median_price_T - median_price_T10) / 10
"""

import logging
import statistics
from sqlalchemy import select, func
from backend.models import Listing, DepreciationEstimate
import backend.db as db
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def compute_all(cfg: dict) -> None:
    session = db.get_session()
    try:
        for v in cfg.get("vehicles", []):
            make, model = v["make"], v["model"]
            base_year = v.get("year_max") or v.get("year_min")
            if not base_year:
                continue
            estimate = _compute(session, make, model, base_year)
            if estimate:
                _upsert(session, estimate)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Depreciation computation failed")
        raise
    finally:
        session.close()


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
    stmt = (
        insert(DepreciationEstimate)
        .values(**est, computed_at=datetime.now(timezone.utc))
        .on_conflict_do_update(
            index_elements=["make", "model", "base_year"],
            set_={
                "rate_5yr": est["rate_5yr"],
                "rate_10yr": est["rate_10yr"],
                "computed_at": datetime.now(timezone.utc),
            },
        )
    )
    session.execute(stmt)
