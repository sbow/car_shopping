-- Add distance_miles to listings (distance from search ZIP at scrape time)
ALTER TABLE listings ADD COLUMN IF NOT EXISTS distance_miles INT;
