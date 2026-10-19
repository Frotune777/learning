-- V003__price_semantics.sql: Add price semantics and source reference to fact_price_daily

ALTER TABLE fact_price_daily ADD COLUMN IF NOT EXISTS price_semantics VARCHAR(20) DEFAULT 'unadjusted';
ALTER TABLE fact_price_daily ADD COLUMN IF NOT EXISTS source_ref VARCHAR(50);
