-- Migration: Add survival_channels column to config table
-- Run this migration on existing databases

-- Add survival_channels column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'config'
        AND column_name = 'survival_channels'
    ) THEN
        ALTER TABLE config ADD COLUMN survival_channels BIGINT[] DEFAULT '{}';
        RAISE NOTICE 'Added survival_channels column to config table';
    ELSE
        RAISE NOTICE 'survival_channels column already exists';
    END IF;
END $$;
