"""SQLAlchemy ORM models."""

import hashlib
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from backend.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vin: Mapped[str | None] = mapped_column(String)
    make: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int | None] = mapped_column(Integer)
    mileage: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)
    fingerprint: Mapped[str | None] = mapped_column(String, unique=True)
    distance_miles: Mapped[int | None] = mapped_column(Integer)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    @staticmethod
    def make_fingerprint(make: str, model: str, year: int, mileage: int | None, price: int | None) -> str:
        key = f"{make}|{model}|{year}|{mileage}|{price}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class DepreciationEstimate(Base):
    __tablename__ = "depreciation_estimates"
    __table_args__ = (UniqueConstraint("make", "model", "base_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    make: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    base_year: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_5yr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    rate_10yr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    rate_r: Mapped[float | None] = mapped_column(Numeric(6, 4))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MarketPriceSnapshot(Base):
    __tablename__ = "market_price_snapshots"
    __table_args__ = (UniqueConstraint("make", "model", "year", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    make: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    median_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AlertSent(Base):
    __tablename__ = "alerts_sent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("listings.id"))
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
