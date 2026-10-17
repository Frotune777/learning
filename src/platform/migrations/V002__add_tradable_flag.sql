-- V002__add_tradable_flag.sql: Add tradability, listing board, and delisting metadata to dim_symbol

ALTER TABLE dim_symbol ADD COLUMN IF NOT EXISTS is_tradable BOOLEAN DEFAULT TRUE;
ALTER TABLE dim_symbol ADD COLUMN IF NOT EXISTS listing_board VARCHAR DEFAULT 'Main';
ALTER TABLE dim_symbol ADD COLUMN IF NOT EXISTS delisting_date DATE;

CREATE INDEX IF NOT EXISTS idx_dim_symbol_tradable ON dim_symbol (is_current, is_tradable);
