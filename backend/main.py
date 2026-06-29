"""Entry point: runs the scraper and alert scheduler."""

import logging
import time
import backend.config as config
import backend.db as db
from backend.scraper.runner import run as scrape
from backend.processor.depreciation import compute_all
from backend.alerts.sms import run as send_alerts

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = config.load()
    db.init(cfg["database_url"])
    interval = cfg.get("scraper", {}).get("interval_minutes", 60) * 60

    logger.info("Car shopping daemon started. Interval: %ds", interval)
    while True:
        logger.info("Starting scrape pass...")
        scrape(cfg)
        logger.info("Computing depreciation estimates...")
        compute_all(cfg)
        logger.info("Checking alerts...")
        send_alerts(cfg)
        logger.info("Pass complete. Sleeping %ds.", interval)
        time.sleep(interval)


if __name__ == "__main__":
    main()
