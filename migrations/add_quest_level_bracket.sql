-- Add level_bracket column to quests table
-- Migration: Add level bracket tracking to quests

-- Add level_bracket column (with a default value for existing rows)
ALTER TABLE quests
ADD COLUMN IF NOT EXISTS level_bracket VARCHAR(20) DEFAULT '3-4';

-- Remove the default after adding the column (new rows must specify level_bracket)
ALTER TABLE quests
ALTER COLUMN level_bracket DROP DEFAULT;

-- Set NOT NULL constraint
ALTER TABLE quests
ALTER COLUMN level_bracket SET NOT NULL;
