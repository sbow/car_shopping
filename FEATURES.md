# Feature List

## MVP (in scope for first working version)

- [x] TOML config file for vehicles of interest, price/mileage range, alert thresholds, scrape interval
- [x] PostgreSQL schema (listings, depreciation_estimates, alerts_sent)
- [x] CarGurus listing scraper (Playwright headless)
- [x] Listing deduplication by fingerprint (VIN or make+model+year+mileage+price hash)
- [x] Depreciation estimator — $/yr via 5yr and 10yr median price comparison
- [x] Alternative vehicle generator — segment map in config.toml
- [x] FastAPI backend — /listings, /watchlist, /depreciation, /alternatives
- [x] Node.js/Express dashboard — watchlist, listings (filtered), depreciation, alternatives views
- [x] SMS alerts via Twilio — underpriced listing detection with 24hr cooldown
- [x] `init.sh` bootstrap script
- [x] `.env` + `.env.example` secrets management
- [x] `config.toml` + `config.toml.example`
- [x] ZIP code and search radius in config.toml (gitignored, not in example)
- [x] Distance scraping — parse miles from listing location text
- [x] Dashboard sortable columns — price, mileage, year, distance, scraped_at
- [x] Scraper selector tuning — CarGurus DOM verified; entity IDs hardcoded (XTS=d2141, CT6=d2352, Volt=d2012)
- [x] Cars.com scraper — Playwright + fuse-card JSON extraction, location from parent li text
- [x] Edmunds scraper — playwright-stealth attempt; graceful 403 fallback, debug_edmunds.html saved
- [x] Multi-source runner — dispatches to cargurus/carscom/edmunds by config.toml sources list
- [x] End-to-end smoke test — scrape → DB → dashboard → SMS (Twilio SID confirmed, 59 listings in dashboard)

- [x] Estimated Cost of Ownership — $/month panel combining depreciation + fuel (EPA MPG/MPGe via fueleconomy.gov API)

## Backlog / Future

- [ ] CT6 trim filtering — filter by "3.6L" engine trim at scraper or post-processing level
- [ ] AutoTrader scraper — second source (sources list in config already supports it)
- [ ] Price history tracking — store price changes per listing over time
- [ ] Depreciation curve chart — visual graph on dashboard (e.g. Chart.js)
- [ ] Price drop alerts — detect when a previously-seen listing drops in price
- [ ] Mileage-adjusted value score — $/mile metric for fairer cross-listing comparison
- [ ] VIN decode — enrich listings with options/trim from NHTSA or similar free API
- [ ] Docker containerization of backend + frontend (full compose stack)
- [ ] Unit tests for depreciation estimator and alternative generator
