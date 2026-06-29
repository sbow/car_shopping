"""FastAPI application — serves listing data to the Node.js dashboard."""

from fastapi import FastAPI, Query
from sqlalchemy import select, asc, desc, nulls_last
from backend.models import Listing, DepreciationEstimate
import backend.db as db
import backend.config as config
from backend.processor.alternatives import get_alternatives

app = FastAPI(title="Car Shopping API")

_cfg: dict = {}

_SORT_COLUMNS = {
    "price": Listing.price,
    "mileage": Listing.mileage,
    "year": Listing.year,
    "distance": Listing.distance_miles,
    "scraped_at": Listing.scraped_at,
}


@app.on_event("startup")
def startup() -> None:
    global _cfg
    _cfg = config.load()
    db.init(_cfg["database_url"])


@app.get("/api/listings")
def listings(
    make: str | None = None,
    model: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    sort_by: str = Query(default="price", pattern="^(price|mileage|year|distance|scraped_at)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=200, le=500),
):
    session = db.get_session()
    try:
        q = select(Listing)
        if make:
            q = q.where(Listing.make == make)
        if model:
            q = q.where(Listing.model == model)
        if year_min:
            q = q.where(Listing.year >= year_min)
        if year_max:
            q = q.where(Listing.year <= year_max)
        if min_price:
            q = q.where(Listing.price >= min_price)
        if max_price:
            q = q.where(Listing.price <= max_price)

        col = _SORT_COLUMNS.get(sort_by, Listing.price)
        order = asc(col) if sort_dir == "asc" else desc(col)
        q = q.order_by(nulls_last(order)).limit(limit)

        rows = session.execute(q).scalars().all()
        return [_listing_dict(r) for r in rows]
    finally:
        session.close()


@app.get("/api/depreciation")
def depreciation(make: str | None = None, model: str | None = None):
    session = db.get_session()
    try:
        q = select(DepreciationEstimate)
        if make:
            q = q.where(DepreciationEstimate.make == make)
        if model:
            q = q.where(DepreciationEstimate.model == model)
        rows = session.execute(q).scalars().all()
        return [
            {"make": r.make, "model": r.model, "base_year": r.base_year,
             "rate_5yr": float(r.rate_5yr) if r.rate_5yr else None,
             "rate_10yr": float(r.rate_10yr) if r.rate_10yr else None}
            for r in rows
        ]
    finally:
        session.close()


@app.get("/api/alternatives")
def alternatives():
    session = db.get_session()
    try:
        return get_alternatives(_cfg, session)
    finally:
        session.close()


@app.get("/api/watchlist")
def watchlist():
    """Best current listing for each configured vehicle."""
    session = db.get_session()
    try:
        results = []
        for v in _cfg.get("vehicles", []):
            q = (
                select(Listing)
                .where(Listing.make == v["make"], Listing.model == v["model"])
                .order_by(Listing.price.asc())
                .limit(3)
            )
            rows = session.execute(q).scalars().all()
            results.append({"vehicle": v, "best_listings": [_listing_dict(r) for r in rows]})
        return results
    finally:
        session.close()


def _listing_dict(r: Listing) -> dict:
    return {
        "id": r.id, "vin": r.vin, "make": r.make, "model": r.model, "year": r.year,
        "price": r.price, "mileage": r.mileage, "location": r.location,
        "distance_miles": r.distance_miles,
        "source": r.source, "source_url": r.source_url,
        "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
    }
