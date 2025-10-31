-- Migration: Add character_creation_roles column to config table
-- Run this migration on existing databases

-- Add character_creation_roles column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'config'
        AND column_name = 'character_creation_roles'
    ) THEN
        ALTER TABLE config ADD COLUMN character_creation_roles BIGINT[] DEFAULT '{}';
        RAISE NOTICE 'Added character_creation_roles column to config table';
    ELSE
        RAISE NOTICE 'character_creation_roles column already exists';
    END IF;
END $$;
