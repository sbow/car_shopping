-- Initial schema for car_shopping

CREATE TABLE IF NOT EXISTS vehicles_of_interest (
    id          SERIAL PRIMARY KEY,
    make        TEXT NOT NULL,
    model       TEXT NOT NULL,
    year_min    INT,
    year_max    INT,
    max_price   INT,
    max_mileage INT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS listings (
    id          SERIAL PRIMARY KEY,
    vin         TEXT,
    make        TEXT NOT NULL,
    model       TEXT NOT NULL,
    year        INT NOT NULL,
    price       INT,
    mileage     INT,
    location    TEXT,
    source      TEXT,
    source_url  TEXT,
    fingerprint TEXT UNIQUE,  -- hash(make+model+year+mileage+price) for VIN-less dedup
    scraped_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listings_make_model_year ON listings (make, model, year);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings (price);

CREATE TABLE IF NOT EXISTS depreciation_estimates (
    id          SERIAL PRIMARY KEY,
    make        TEXT NOT NULL,
    model       TEXT NOT NULL,
    base_year   INT NOT NULL,
    rate_5yr    NUMERIC(10,2),  -- $/yr over 5-year window
    rate_10yr   NUMERIC(10,2), -- $/yr over 10-year window
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (make, model, base_year)
);

CREATE TABLE IF NOT EXISTS alerts_sent (
    id          SERIAL PRIMARY KEY,
    listing_id  INT REFERENCES listings(id),
    alert_type  TEXT NOT NULL,  -- 'price_drop', 'new_listing', 'underpriced'
    recipient   TEXT NOT NULL,
    sent_at     TIMESTAMPTZ DEFAULT NOW()
);
