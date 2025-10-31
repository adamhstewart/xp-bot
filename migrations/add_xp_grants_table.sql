-- Migration: Add xp_grants table for audit trail
-- Run this migration on existing databases

-- Create xp_grants table
CREATE TABLE IF NOT EXISTS xp_grants (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    granted_by_user_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    memo TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_xp_grants_character_id ON xp_grants(character_id);
CREATE INDEX IF NOT EXISTS idx_xp_grants_granted_by ON xp_grants(granted_by_user_id);
