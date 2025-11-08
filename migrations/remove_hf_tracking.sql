-- Migration: Remove HF tracking system
-- Run this migration to clean up the old HF (hunting/fishing) tracking columns

-- Drop HF-related columns from config table
ALTER TABLE config DROP COLUMN IF EXISTS hf_channels;
ALTER TABLE config DROP COLUMN IF EXISTS hf_attempt_xp;
ALTER TABLE config DROP COLUMN IF EXISTS hf_success_xp;
ALTER TABLE config DROP COLUMN IF EXISTS daily_hf_cap;

-- Drop HF-related column from characters table
ALTER TABLE characters DROP COLUMN IF EXISTS daily_hf;
