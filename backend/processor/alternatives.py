"""Generate alternative vehicle suggestions based on segment mapping in config."""

import logging
from sqlalchemy import select, func
from backend.models import Listing

logger = logging.getLogger(__name__)


def get_alternatives(cfg: dict, session) -> list[dict]:
    """Return best listings for vehicles in the same segment as configured targets."""
    segments: dict[str, list[str]] = cfg.get("segments", {})
    results = []

    for v in cfg.get("vehicles", []):
        key = f"{v['make']} {v['model']}"
        alts = segments.get(key, [])
        for alt in alts:
            parts = alt.split(" ", 1)
            if len(parts) != 2:
                continue
            alt_make, alt_model = parts
            best = _best_listing(session, alt_make, alt_model,
                                 v.get("year_min"), v.get("year_max"),
                                 v.get("min_price"), v.get("max_price"),
                                 v.get("max_mileage"))
            if best:
                results.append({
                    "for_vehicle": key,
                    "alternative": alt,
                    **best,
                })
    return results


def _best_listing(session, make: str, model: str,
                  year_min: int | None, year_max: int | None,
                  min_price: int | None, max_price: int | None,
                  max_mileage: int | None) -> dict | None:
    q = select(Listing).where(Listing.make == make, Listing.model == model)
    if year_min:
        q = q.where(Listing.year >= year_min)
    if year_max:
        q = q.where(Listing.year <= year_max)
    if min_price:
        q = q.where(Listing.price >= min_price)
    if max_price:
        q = q.where(Listing.price <= max_price)
    if max_mileage:
        q = q.where(Listing.mileage <= max_mileage)
    q = q.order_by(Listing.price.asc()).limit(1)

    row = session.execute(q).scalar_one_or_none()
    if not row:
        return None
    return {
        "make": row.make, "model": row.model, "year": row.year,
        "price": row.price, "mileage": row.mileage,
        "source_url": row.source_url,
    }
