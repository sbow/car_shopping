"""Scrape all vehicles of interest and upsert into the database."""

import logging
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import insert
from backend.scraper.cargurus import CarGurusScraper
from backend.scraper.carscom import CarsDotComScraper
from backend.scraper.edmunds import EdmundsScraper
from backend.scraper.base import BaseScraper
from backend.models import Listing
import backend.db as db

logger = logging.getLogger(__name__)

_SCRAPERS: dict[str, type[BaseScraper]] = {
    "cargurus": CarGurusScraper,
    "carscom": CarsDotComScraper,
    "edmunds": EdmundsScraper,
}


def run(cfg: dict) -> None:
    """Run a full scrape pass for all configured vehicles and sources."""
    scraper_cfg = cfg.get("scraper", {})
    zip_code = scraper_cfg.get("zip", "00000")
    radius_miles = scraper_cfg.get("radius_miles", 100)
    sources = scraper_cfg.get("sources", ["cargurus"])

    session = db.get_session()
    try:
        for v in cfg.get("vehicles", []):
            make, model = v["make"], v["model"]
            for source_name in sources:
                scraper_cls = _SCRAPERS.get(source_name)
                if not scraper_cls:
                    logger.warning("Unknown scraper source: %s", source_name)
                    continue
                scraper = scraper_cls()
                logger.info("Scraping %s %s via %s", make, model, source_name)
                listings = scraper.scrape(
                    make=make,
                    model=model,
                    year_min=v.get("year_min", 2000),
                    year_max=v.get("year_max", 2030),
                    min_price=v.get("min_price"),
                    max_price=v.get("max_price"),
                    max_mileage=v.get("max_mileage"),
                    zip_code=zip_code,
                    radius_miles=radius_miles,
                )
                logger.info("Got %d listings for %s %s from %s",
                            len(listings), make, model, source_name)
                _upsert_listings(session, listings)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Scrape run failed")
        raise
    finally:
        session.close()


def _upsert_listings(session, raw_listings) -> None:
    now = datetime.now(timezone.utc)
    for r in raw_listings:
        fp = Listing.make_fingerprint(r.make, r.model, r.year, r.mileage, r.price)
        stmt = (
            insert(Listing)
            .values(
                vin=r.vin, make=r.make, model=r.model, year=r.year,
                price=r.price, mileage=r.mileage, location=r.location,
                source=r.source, source_url=r.source_url, fingerprint=fp,
                distance_miles=r.distance_miles,
            )
            .on_conflict_do_update(
                index_elements=["fingerprint"],
                set_={"price": r.price, "distance_miles": r.distance_miles, "updated_at": now},
            )
        )
        session.execute(stmt)
