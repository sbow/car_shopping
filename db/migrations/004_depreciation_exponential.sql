-- Exponential decay depreciation model + cross-sectional market price data

ALTER TABLE depreciation_estimates
    ADD COLUMN IF NOT EXISTS rate_r NUMERIC(6,4);  -- annual decay rate (e.g. 0.1312 = 13.12%/yr)

CREATE TABLE IF NOT EXISTS market_price_snapshots (
    id           SERIAL PRIMARY KEY,
    make         TEXT NOT NULL,
    model        TEXT NOT NULL,
    year         INTEGER NOT NULL,
    median_price NUMERIC(10,2) NOT NULL,
    source       TEXT NOT NULL,          -- 'iseecars'
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (make, model, year, source)
);

CREATE INDEX IF NOT EXISTS idx_mps_make_model ON market_price_snapshots (make, model);
