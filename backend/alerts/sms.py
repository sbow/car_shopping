"""SMS alert dispatch via Twilio."""

import logging
from datetime import datetime, timezone, timedelta
from twilio.rest import Client
from sqlalchemy import select, func
from backend.models import Listing, AlertSent, DepreciationEstimate
import backend.db as db

logger = logging.getLogger(__name__)

_COOLDOWN_HOURS = 24  # Don't re-alert on the same listing within this window


def run(cfg: dict) -> None:
    threshold_pct = cfg.get("alerts", {}).get("price_drop_threshold_pct", 5)
    recipients = cfg.get("alerts", {}).get("sms_recipients", [])
    twilio_cfg = cfg["twilio"]

    client = Client(twilio_cfg["account_sid"], twilio_cfg["auth_token"])
    session = db.get_session()

    try:
        for v in cfg.get("vehicles", []):
            _check_new_underpriced(session, client, twilio_cfg, recipients, v)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Alert run failed")
        raise
    finally:
        session.close()


def _check_new_underpriced(session, client, twilio_cfg, recipients, v: dict) -> None:
    """Alert on listings that are below the configured max_price."""
    make, model = v["make"], v["model"]
    max_price = v.get("max_price")
    if not max_price:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=_COOLDOWN_HOURS)
    q = (
        select(Listing)
        .where(Listing.make == make, Listing.model == model)
        .where(Listing.price <= max_price * 0.9)  # 10% below threshold = deal
        .where(Listing.scraped_at >= cutoff)
    )
    listings = session.execute(q).scalars().all()

    for listing in listings:
        if _already_alerted(session, listing.id, "underpriced"):
            continue
        msg = (
            f"Deal alert: {listing.year} {listing.make} {listing.model} "
            f"at ${listing.price:,} ({listing.mileage:,} mi) — {listing.source_url}"
        )
        for recipient in recipients:
            _send_sms(client, twilio_cfg["from_number"], recipient, msg)
            _record_alert(session, listing.id, "underpriced", recipient)
            logger.info("Alert sent to %s: %s", recipient, msg)


def _already_alerted(session, listing_id: int, alert_type: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_COOLDOWN_HOURS)
    count = session.execute(
        select(func.count()).select_from(AlertSent)
        .where(AlertSent.listing_id == listing_id)
        .where(AlertSent.alert_type == alert_type)
        .where(AlertSent.sent_at >= cutoff)
    ).scalar()
    return (count or 0) > 0


def _send_sms(client: Client, from_: str, to: str, body: str) -> None:
    client.messages.create(body=body, from_=from_, to=to)


def _record_alert(session, listing_id: int, alert_type: str, recipient: str) -> None:
    session.add(AlertSent(listing_id=listing_id, alert_type=alert_type, recipient=recipient))
