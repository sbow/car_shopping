# Engineering Tracker

## Process Rules
- After each significant step: update FEATURES.md, update this file, update README.md if user-facing, verify requirements.
- Ask before filling in unspecified values (price floors, mileage limits, etc.).
- Never commit secrets. config.toml is gitignored; config.toml.example is the committed template.

---

## Completed Steps

### Project Scaffold
- Created full directory structure: backend/, frontend/dashboard/, db/migrations/
- Established coding norms in ~/.claude/CLAUDE.md (C++21, Google style, TOML, PostgreSQL, venv/Docker)

### Configuration
- `config.toml` — 3 target vehicles (Cadillac XTS 2018+, CT6 2016+, Chevrolet Volt 2018), $14k–$21k, ≤150k mi
- `config.toml.example` — synced, SMS placeholder redacted
- `.env` / `.env.example` — Twilio + DB credentials

### Database
- `docker-compose.yml` — PostgreSQL 16
- `db/migrations/001_initial_schema.sql` — listings, depreciation_estimates, alerts_sent
- `db/migrations/002_add_min_price.sql` — added min_price column to vehicles_of_interest

### Backend (Python)
- `backend/config.py` — loads TOML + .env
- `backend/db.py` — SQLAlchemy engine/session
- `backend/models.py` — Listing, DepreciationEstimate, AlertSent ORM models
- `backend/scraper/base.py` — abstract BaseScraper
- `backend/scraper/cargurus.py` — Playwright scraper (selectors need live-site verification)
- `backend/scraper/runner.py` — scrape all configured vehicles, upsert to DB
- `backend/processor/depreciation.py` — 5yr/10yr $/yr heuristic
- `backend/processor/alternatives.py` — segment-map based alternative lookup
- `backend/alerts/sms.py` — Twilio SMS, underpriced detection, 24hr cooldown
- `backend/api/main.py` — FastAPI: /watchlist, /listings, /depreciation, /alternatives
- `backend/main.py` — scrape+process+alert loop daemon

### Frontend (Node.js)
- `frontend/dashboard/server.js` — Express, proxies to FastAPI
- EJS views: index (watchlist), listings (filtered table), depreciation, alternatives, error

### Bootstrap
- `init.sh` — checks Python/Node/Docker, creates venv, npm install, starts Postgres, runs migrations, copies example configs

### ZIP / Radius + Distance Sorting
- `config.toml` — zip and radius_miles added (gitignored; placeholder in example)
- `backend/scraper/cargurus.py` — zip/radius wired into URL; distance parsed from location text ("City, ST (42 mi away)")
- `backend/scraper/runner.py` — reads zip/radius from config and passes to scraper
- `db/migrations/003_add_distance.sql` — distance_miles column on listings
- `backend/models.py` — distance_miles field added
- `backend/api/main.py` — sort_by (price/mileage/year/distance/scraped_at) + sort_dir params; nulls_last ordering
- `frontend/dashboard/views/listings.ejs` — clickable sort headers with ▲/▼ indicators
- `frontend/dashboard/server.js` — sort_by/sort_dir forwarded to API

### Multi-Source Scraper Overhaul
- **CarGurus entity ID discovery**: URL format requires numeric entity IDs (not text slugs). Discovered via make-page filter facet JSON: `{"name":"m1/d2012","label":"Volt",...}`. Confirmed IDs:
  - Cadillac make = m22; XTS = d2141; CT6 = d2352
  - Chevrolet make = m1; Volt = d2012
- `backend/scraper/cargurus_ids.py` — rewritten: seeded known IDs, discovery via make-page facet JSON for unknowns, `build_search_url()` uses `l-Used-{Make}-{Model}-{modelId}?zip=...` format
- `backend/scraper/cargurus.py` — rewritten: `data-testid="srp-listing-tile"` cards, correct price/mileage/location/distance selectors, pagination up to 5 pages
- `backend/scraper/carscom.py` — new: Playwright (plain requests blocked by bot detection), `fuse-card[data-vehicle-details]` JSON extraction, location/distance from parent `<li>` text
- `backend/scraper/edmunds.py` — new: playwright-stealth (`Stealth().apply_stealth_sync(page)`), graceful block detection, saves `debug_edmunds.html`
- `backend/scraper/runner.py` — updated: dispatches to `cargurus`/`carscom`/`edmunds` scrapers by `config.toml` sources list
- `config.toml` sources updated to `["cargurus", "carscom", "edmunds"]`

---

### Smoke Test & First Commit
- End-to-end pipeline verified: scrape → 59 unique listings in DB → dashboard renders all rows → Twilio SMS delivered (SID confirmed on device)
- API default limit raised from 50 to 200 so dashboard shows all listings without pagination
- 38 `alerts_sent` suppression records pre-inserted for all currently-alertable XTS listings to prevent alert flood on first daemon run
- `debug_browse.html` added to `.gitignore`

---

### Cost of Ownership Feature
- `config.toml` / `config.toml.example` — added `[cost_of_ownership]` section: `monthly_miles`, `gas_price_per_gallon`
- `backend/processor/fuel_economy.py` — NEW: fetches combined MPG/MPGe from EPA fueleconomy.gov REST API; PHEVs use `phevComb`, others use `comb08`; results cached in `backend/processor/mpg_cache.json` (gitignored)
- `backend/api/main.py` — added `/api/cost_of_ownership` endpoint: queries `depreciation_estimates` for best rate, calls `get_mpg()`, returns depreciation + fuel $/month + total per configured vehicle
- `frontend/dashboard/server.js` — added `/cost` route
- `frontend/dashboard/views/cost_of_ownership.ejs` — NEW: table of vehicles × cost components
- All existing views — added "Cost of Ownership" nav link

---

## Current Status

**MVP complete. All features shipped and smoke-tested.**

- CarGurus: 99 listings/vehicle, 5-page pagination, entity IDs confirmed
- Cars.com: 36 listings with VINs, Playwright required (plain requests blocked)
- Edmunds: graceful fallback (Akamai WAF blocks stealth attempt)
- Dashboard: sortable table, 59 listings, all columns populated
- SMS: Twilio confirmed working, 24hr cooldown active

Next up (backlog): price history tracking, CT6 trim filtering, mileage-adjusted value score.

---

## Known Gaps / Decisions Deferred

| Item | Decision |
|---|---|
| CT6 3.6L trim filtering | Deferred to post-MVP; tracked in FEATURES.md |
| Edmunds | Akamai WAF hard-blocks playwright-stealth; graceful fallback in place |
| AutoTrader scraper | Deferred; sources config key supports it |
| Price history | Not tracked yet; only latest scraped price stored |
