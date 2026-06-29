"""CarGurus listing scraper using Playwright headless browser."""

import re
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from backend.scraper.base import BaseScraper, RawListing
from backend.scraper.cargurus_ids import get_entity_ids, build_search_url

logger = logging.getLogger(__name__)

_DEBUG_HTML = Path(__file__).parents[2] / "debug_last_page.html"
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
_MAX_PAGES = 5


class CarGurusScraper(BaseScraper):
    """Scrape used car listings from CarGurus.

    Uses a headless browser because CarGurus is a JS-rendered SPA.
    Rate-limit responsibly — one vehicle search per invocation.
    """

    def scrape(self, make: str, model: str, year_min: int, year_max: int,
               min_price: int | None, max_price: int | None,
               max_mileage: int | None, zip_code: str = "00000",
               radius_miles: int = 100) -> list[RawListing]:
        make_id, model_id = get_entity_ids(make, model)
        if not model_id:
            logger.error("CarGurus: no entity ID for %s %s — skipping", make, model)
            return []

        url = build_search_url(
            make, model, make_id, model_id,
            zip_code, radius_miles, year_min, year_max,
            min_price, max_price, max_mileage,
        )
        logger.info("CarGurus scraping: %s", url)

        listings: list[RawListing] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 900})
            page = context.new_page()
            try:
                listings = self._scrape_all_pages(page, url, make, model)
            except Exception:
                logger.exception("CarGurus scrape failed for %s %s", make, model)
                try:
                    _DEBUG_HTML.write_text(page.content(), encoding="utf-8")
                except Exception:
                    pass
            finally:
                browser.close()
        return listings

    def _scrape_all_pages(self, page: Page, first_url: str,
                          make: str, model: str) -> list[RawListing]:
        results: list[RawListing] = []
        url = first_url
        for page_num in range(1, _MAX_PAGES + 1):
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            html = page.content()
            if page_num == 1:
                _DEBUG_HTML.write_text(html, encoding="utf-8")
                logger.info("Page HTML saved to %s (%d bytes)", _DEBUG_HTML, len(html))
            batch = self._parse_page(html, make, model)
            logger.info("Page %d: %d listings for %s %s", page_num, len(batch), make, model)
            results.extend(batch)
            if not batch:
                break
            next_url = self._next_page_url(page, url, page_num)
            if not next_url:
                break
            url = next_url
        return results

    def _parse_page(self, html: str, make: str, model: str) -> list[RawListing]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all(attrs={"data-testid": "srp-listing-tile"})
        logger.info("Found %d listing tiles", len(cards))
        results = []
        for card in cards:
            try:
                title_el = card.find(attrs={"data-testid": "srp-listing-blade-title"})
                price_el = card.find(attrs={"data-testid": "srp-tile-price"})
                mileage_el = card.find(attrs={"data-testid": "srp-tile-mileage"})
                loc1_el = card.find(attrs={"data-testid": "LocationSection-firstLine"})
                loc2_el = card.find(attrs={"data-testid": "LocationSection-secondLine"})
                link_el = card.find("a", attrs={"data-testid": "tile-link"})

                year = self._parse_year(title_el.get_text() if title_el else None)
                price = self._parse_int(price_el.get_text() if price_el else None)
                mileage = self._parse_int(mileage_el.get_text() if mileage_el else None)
                location = loc1_el.get_text(strip=True) if loc1_el else None
                distance_miles = self._parse_distance(
                    loc2_el.get_text() if loc2_el else None
                )
                href = link_el.get("href", "") if link_el else ""
                source_url = f"https://www.cargurus.com{href.split('?')[0]}" if href else ""

                if year:
                    results.append(RawListing(
                        make=make, model=model, year=year,
                        price=price, mileage=mileage,
                        location=location, vin=None,
                        source_url=source_url, source="cargurus",
                        distance_miles=distance_miles,
                    ))
            except Exception:
                logger.debug("Failed to parse card", exc_info=True)
        return results

    @staticmethod
    def _next_page_url(page: Page, current_url: str, page_num: int) -> str | None:
        """Return the URL for the next page, or None if on the last page."""
        try:
            next_btn = page.query_selector('a[aria-label="Next page"], button[aria-label="Next page"]')
            if not next_btn:
                return None
            disabled = next_btn.get_attribute("aria-disabled") or next_btn.get_attribute("disabled")
            if disabled and disabled != "false":
                return None
            # Append/replace page param
            base = current_url.split("&page=")[0]
            return f"{base}&page={page_num + 1}"
        except Exception:
            return None

    @staticmethod
    def _parse_distance(text: str | None) -> int | None:
        if not text:
            return None
        m = re.search(r"(\d+)\s*mi", text)
        return int(m.group(1)) if m else None

    @staticmethod
    def _parse_int(text: str | None) -> int | None:
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    @staticmethod
    def _parse_year(text: str | None) -> int | None:
        if not text:
            return None
        m = re.search(r"\b(19|20)\d{2}\b", text)
        return int(m.group()) if m else None
