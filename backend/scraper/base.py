"""Abstract base class for listing scrapers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawListing:
    make: str
    model: str
    year: int
    price: int | None
    mileage: int | None
    location: str | None
    vin: str | None
    source_url: str
    source: str
    distance_miles: int | None = None


class BaseScraper(ABC):
    """Scrape listings for a single vehicle spec."""

    @abstractmethod
    def scrape(self, make: str, model: str, year_min: int, year_max: int,
               min_price: int | None, max_price: int | None,
               max_mileage: int | None, zip_code: str = "00000",
               radius_miles: int = 100) -> list[RawListing]:
        ...
