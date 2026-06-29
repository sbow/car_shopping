"""Cars.com listing scraper using Playwright + BeautifulSoup.

Cars.com embeds all listing data as JSON in a ``data-vehicle-details``
attribute on each ``<fuse-card>`` element.  A headless browser is required
because Cars.com blocks plain HTTP clients.
"""

import json
import logging
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from backend.scraper.base import BaseScraper, RawListing

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
_BASE_URL = "https://www.cars.com/shopping/results/"
_PAGE_SIZE = 20
_MAX_PAGES = 10


class CarsDotComScraper(BaseScraper):
    """Scrape used car listings from Cars.com."""

    def scrape(self, make: str, model: str, year_min: int, year_max: int,
               min_price: int | None, max_price: int | None,
               max_mileage: int | None, zip_code: str = "00000",
               radius_miles: int = 100) -> list[RawListing]:
        make_slug = make.lower().replace(" ", "-")
        model_slug = f"{make_slug}-{model.lower().replace(' ', '-')}"
        results: list[RawListing] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                user_agent=_UA,
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            try:
                for page_num in range(1, _MAX_PAGES + 1):
                    url = self._build_url(make_slug, model_slug, zip_code, radius_miles,
                                          year_min, year_max, min_price, max_price,
                                          max_mileage, page_num)
                    logger.info("Cars.com page %d: %s", page_num, url)
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(4000)
                    html = page.content()
                    batch = self._parse_page(html, make, model)
                    logger.info("Cars.com page %d: %d listings", page_num, len(batch))
                    results.extend(batch)
                    if len(batch) < _PAGE_SIZE:
                        break
            except Exception:
                logger.exception("Cars.com scrape failed for %s %s", make, model)
            finally:
                browser.close()

        return results

    @staticmethod
    def _build_url(make_slug: str, model_slug: str, zip_code: str,
                   radius_miles: int, year_min: int, year_max: int,
                   min_price: int | None, max_price: int | None,
                   max_mileage: int | None, page: int) -> str:
        params: list[str] = [
            f"makes[]={make_slug}",
            f"models[]={model_slug}",
            f"zip={zip_code}",
            f"maximum_distance={radius_miles}",
            f"year_min={year_min}",
            f"year_max={year_max}",
            "stock_type=used",
            "sort=list_price_asc",
            f"page={page}",
        ]
        if min_price:
            params.append(f"list_price_min={min_price}")
        if max_price:
            params.append(f"list_price_max={max_price}")
        if max_mileage:
            params.append(f"mileage_max={max_mileage}")
        # Cars.com uses literal [] in query params (not URL-encoded)
        qs = "&".join(params)
        return f"{_BASE_URL}?{qs}"

    @staticmethod
    def _parse_page(html: str, make: str, model: str) -> list[RawListing]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("fuse-card", attrs={"data-vehicle-details": True})
        results = []
        for card in cards:
            raw = card.get("data-vehicle-details", "")
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                logger.debug("Failed to parse data-vehicle-details JSON")
                continue
            try:
                year_val = data.get("year")
                year = int(year_val) if year_val else None
                if not year:
                    continue

                price_str = data.get("price") or data.get("list_price", "")
                mileage_str = data.get("mileage", "")
                vin = data.get("vin") or None
                # Location and distance come from the surrounding <li> text
                parent_text = card.parent.get_text(" ", strip=True) if card.parent else ""
                location, distance_miles = _parse_location_from_text(parent_text)
                source_url = _listing_url(data)
                price = _parse_int(str(price_str))
                mileage = _parse_int(str(mileage_str))

                results.append(RawListing(
                    make=make, model=model, year=year,
                    price=price, mileage=mileage,
                    location=location, vin=vin,
                    source_url=source_url, source="carscom",
                    distance_miles=distance_miles,
                ))
            except Exception:
                logger.debug("Failed to parse Cars.com card", exc_info=True)
        return results


def _parse_location_from_text(text: str) -> tuple[str | None, int | None]:
    """Extract 'City, ST (N mi)' from the card's surrounding li text.

    The city always appears after the dealer name, so we take the last match.
    City names are at most 3 words to avoid capturing long dealer names.
    """
    _CITY_RE = re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,1}),\s*([A-Z]{2})\s*\((\d+)\s*mi\)"
    )
    matches = list(_CITY_RE.finditer(text))
    if matches:
        m = matches[-1]  # last match = the actual city
        return f"{m.group(1)}, {m.group(2)}", int(m.group(3))
    # No distance — try without parenthetical
    _CITY_NODIST_RE = re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,1}),\s*([A-Z]{2})\b"
    )
    matches2 = list(_CITY_NODIST_RE.finditer(text))
    if matches2:
        m2 = matches2[-1]
        return f"{m2.group(1)}, {m2.group(2)}", None
    return None, None


def _listing_url(data: dict) -> str:
    listing_id = data.get("listingId") or data.get("listing_id", "")
    if listing_id:
        return f"https://www.cars.com/vehicledetail/{listing_id}/"
    return ""


def _parse_int(text: str) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None
