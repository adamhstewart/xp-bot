-- Migration: Add xp_request_channel column to config table
-- Run this migration on existing databases

-- Add xp_request_channel column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'config'
        AND column_name = 'xp_request_channel'
    ) THEN
        ALTER TABLE config ADD COLUMN xp_request_channel BIGINT;
        RAISE NOTICE 'Added xp_request_channel column to config table';
    ELSE
        RAISE NOTICE 'xp_request_channel column already exists';
    END IF;
END $$;
