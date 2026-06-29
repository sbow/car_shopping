-- Add min_price to vehicles_of_interest and listings filter support
ALTER TABLE vehicles_of_interest ADD COLUMN IF NOT EXISTS min_price INT;
