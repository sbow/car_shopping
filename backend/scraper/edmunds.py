"""Edmunds listing scraper with playwright-stealth bypass attempt.

Edmunds uses Akamai WAF which performs TLS and browser fingerprinting.
This scraper applies playwright-stealth patches to reduce the fingerprint delta.
If Edmunds still blocks the request (403 / bot-challenge page), it logs a
warning and returns an empty list so other scrapers run unaffected.
"""

import re
import json
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
from backend.scraper.base import BaseScraper, RawListing

logger = logging.getLogger(__name__)

_DEBUG_HTML = Path(__file__).parents[2] / "debug_edmunds.html"
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
_MAX_PAGES = 5


class EdmundsScraper(BaseScraper):
    """Scrape used car listings from Edmunds using playwright-stealth."""

    def scrape(self, make: str, model: str, year_min: int, year_max: int,
               min_price: int | None, max_price: int | None,
               max_mileage: int | None, zip_code: str = "00000",
               radius_miles: int = 100) -> list[RawListing]:
        url = self._build_url(make, model, zip_code, radius_miles,
                              year_min, year_max, min_price, max_price, max_mileage)
        logger.info("Edmunds scraping (stealth): %s", url)

        results: list[RawListing] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                user_agent=_UA,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                },
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                html = page.content()
                _DEBUG_HTML.write_text(html, encoding="utf-8")
                logger.info("Edmunds HTML saved (%d bytes)", len(html))

                if self._is_blocked(html):
                    logger.warning(
                        "Edmunds returned a block/challenge page — skipping. "
                        "Check debug_edmunds.html for details."
                    )
                    return []

                results = self._parse_page(html, make, model)
                logger.info("Edmunds: parsed %d listings for %s %s",
                            len(results), make, model)
            except Exception:
                logger.exception("Edmunds scrape failed for %s %s", make, model)
                try:
                    _DEBUG_HTML.write_text(page.content(), encoding="utf-8")
                except Exception:
                    pass
            finally:
                browser.close()
        return results

    @staticmethod
    def _build_url(make: str, model: str, zip_code: str, radius: int,
                   year_min: int, year_max: int,
                   min_price: int | None, max_price: int | None,
                   max_mileage: int | None) -> str:
        make_slug = make.lower().replace(" ", "-")
        model_slug = model.lower().replace(" ", "-")
        params: list[str] = [
            f"zip={zip_code}",
            f"radius={radius}",
            f"year_min={year_min}",
            f"year_max={year_max}",
            "inventorytype=used",
        ]
        if min_price:
            params.append(f"price_min={min_price}")
        if max_price:
            params.append(f"price_max={max_price}")
        if max_mileage:
            params.append(f"mileage_max={max_mileage}")
        qs = "&".join(params)
        return f"https://www.edmunds.com/{make_slug}/{model_slug}/used/?{qs}"

    @staticmethod
    def _is_blocked(html: str) -> bool:
        lower = html.lower()
        return (
            "access denied" in lower
            or "403 forbidden" in lower
            or "robot or human" in lower
            or "_abck" in lower and "vehicle" not in lower
            or len(html) < 5000
        )

    @staticmethod
    def _parse_page(html: str, make: str, model: str) -> list[RawListing]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Edmunds embeds listing data in a JSON script tag
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    items = data
                elif data.get("@type") == "ItemList":
                    items = [i.get("item", i) for i in data.get("itemListElement", [])]
                else:
                    continue
                for item in items:
                    result = EdmundsScraper._extract_listing(item, make, model)
                    if result:
                        results.append(result)
            except (json.JSONDecodeError, AttributeError):
                continue

        if results:
            return results

        # Fallback: parse visible card elements
        cards = soup.find_all("div", attrs={"data-tracking-type": "used"})
        cards = cards or soup.find_all(class_=re.compile(r"vehicle-card|listing-card"))
        for card in cards:
            text = card.get_text(separator=" ", strip=True)
            year_m = re.search(r"\b(20\d{2})\b", text)
            price_m = re.search(r"\$([\d,]+)", text)
            mileage_m = re.search(r"([\d,]+)\s*mi", text)
            if year_m:
                results.append(RawListing(
                    make=make, model=model,
                    year=int(year_m.group(1)),
                    price=int(price_m.group(1).replace(",", "")) if price_m else None,
                    mileage=int(mileage_m.group(1).replace(",", "")) if mileage_m else None,
                    location=None, vin=None,
                    source_url="", source="edmunds",
                ))
        return results

    @staticmethod
    def _extract_listing(item: dict, make: str, model: str) -> RawListing | None:
        try:
            name = item.get("name", "")
            year_m = re.search(r"\b(20\d{2})\b", name)
            if not year_m:
                return None
            year = int(year_m.group(1))
            price_info = item.get("offers", {})
            price_str = price_info.get("price", "") if isinstance(price_info, dict) else ""
            price = int(re.sub(r"[^\d]", "", str(price_str))) if price_str else None
            mileage_str = item.get("mileageFromOdometer", {})
            mileage = None
            if isinstance(mileage_str, dict):
                mileage = int(re.sub(r"[^\d]", "", str(mileage_str.get("value", "")))) or None
            url = item.get("url", "")
            seller = item.get("seller", {}) or {}
            location = seller.get("address", {}).get("addressLocality")
            return RawListing(
                make=make, model=model, year=year,
                price=price, mileage=mileage,
                location=location, vin=item.get("vehicleIdentificationNumber") or None,
                source_url=url, source="edmunds",
            )
        except Exception:
            return None
