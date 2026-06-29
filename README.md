# Car Shopping Tool

A personal vehicle deal-finder. Tracks listings from multiple sources, estimates depreciation, surfaces alternatives, and sends SMS alerts when deals appear.

## Features
- **Multi-source listing scraper** — CarGurus (paginated, 90+ results) and Cars.com (with full VIN data); Edmunds attempted with stealth bypass
- **Listing deduplication** — cross-source fingerprinting prevents duplicates (same listing from CarGurus and Cars.com stored once)
- **Depreciation estimator** — infers $/yr depreciation by comparing prices across model years
- **Alternative generator** — suggests comparable vehicles in the same segment
- **Dashboard** — Node.js/Express web UI with sortable listings (price, mileage, year, distance)
- **SMS alerts** — Twilio-powered notifications for underpriced listings

## Quick Start
```bash
cp .env.example .env              # fill in DB + Twilio credentials
cp config.toml.example config.toml  # fill in your target vehicles and ZIP
./init.sh
```

Then in separate terminals:
```bash
# Start the API
source backend/.venv/bin/activate && uvicorn backend.api.main:app --reload

# Start the dashboard
cd frontend/dashboard && node server.js

# Run a scrape pass
source backend/.venv/bin/activate && python -m backend.main
```

Dashboard: http://localhost:3000

## Configuration
- `config.toml` — target vehicles, price/mileage limits, alert thresholds, scrape interval, sources list, segment map. Gitignored; `config.toml.example` is the committed template.
- `.env` — secrets only (DB URL, Twilio credentials). Gitignored; `.env.example` is the committed template.

## Project Structure
```
backend/
  scraper/
    cargurus.py     # Playwright headless — 90+ results, up to 5 pages
    carscom.py      # Playwright headless — fuse-card JSON, full VIN
    edmunds.py      # playwright-stealth attempt, graceful 403 fallback
    cargurus_ids.py # Entity ID registry (d2141=XTS, d2352=CT6, d2012=Volt)
    runner.py       # Dispatches to scrapers per config.toml sources list
  processor/        # Depreciation estimation, alternative generation
  api/              # FastAPI — /listings, /watchlist, /depreciation, /alternatives
  alerts/           # Twilio SMS dispatch
frontend/
  dashboard/        # Node.js/Express web UI
db/
  migrations/       # SQL schema
```

## Requirements
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

## Known Limitations (MVP)
- Edmunds blocked by Akamai WAF; playwright-stealth not sufficient — fallback returns empty list
- CT6 3.6L trim filtering not enforced at scraper level
- Price history not tracked — only latest scraped price stored per listing
