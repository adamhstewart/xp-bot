-- Migration: Add character_sheet_url column to characters table
-- Run this migration on existing databases

-- Add character_sheet_url column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'characters'
        AND column_name = 'character_sheet_url'
    ) THEN
        ALTER TABLE characters ADD COLUMN character_sheet_url TEXT;
        RAISE NOTICE 'Added character_sheet_url column to characters table';
    ELSE
        RAISE NOTICE 'character_sheet_url column already exists';
    END IF;
END $$;
