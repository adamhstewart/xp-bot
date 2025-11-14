-- XP Bot PostgreSQL Schema

-- Guild configuration (global settings)
CREATE TABLE IF NOT EXISTS config (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    rp_channels BIGINT[] DEFAULT '{}',
    survival_channels BIGINT[] DEFAULT '{}',
    char_per_rp INTEGER DEFAULT 240,
    daily_rp_cap INTEGER DEFAULT 10,
    character_creation_roles BIGINT[] DEFAULT '{}',
    xp_request_channel BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User accounts
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    active_character_id INTEGER,
    timezone VARCHAR(50) DEFAULT 'UTC',
    last_xp_reset DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Characters (many-to-one with users)
CREATE TABLE IF NOT EXISTS characters (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    xp INTEGER DEFAULT 0,
    daily_xp INTEGER DEFAULT 0,
    char_buffer INTEGER DEFAULT 0,
    image_url TEXT,
    character_sheet_url TEXT,
    retired BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Unique constraint only for active (non-retired) characters
CREATE UNIQUE INDEX IF NOT EXISTS idx_characters_user_name_active
    ON characters(user_id, name)
    WHERE retired = FALSE;

-- Add foreign key for active character (must be after characters table exists)
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_active_character;
ALTER TABLE users
    ADD CONSTRAINT fk_active_character
    FOREIGN KEY (active_character_id)
    REFERENCES characters(id) ON DELETE SET NULL;

-- XP grant log (audit trail for manual XP grants)
CREATE TABLE IF NOT EXISTS xp_grants (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    granted_by_user_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    memo TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_characters_user_id ON characters(user_id);
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
CREATE INDEX IF NOT EXISTS idx_characters_retired ON characters(retired);
CREATE INDEX IF NOT EXISTS idx_users_last_reset ON users(last_xp_reset);
CREATE INDEX IF NOT EXISTS idx_xp_grants_character_id ON xp_grants(character_id);
CREATE INDEX IF NOT EXISTS idx_xp_grants_granted_by ON xp_grants(granted_by_user_id);

-- Quest Tracking System
-- Tracks quests/missions with PC participation, DMs, and monsters/CR

-- Main quests table
CREATE TABLE IF NOT EXISTS quests (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name VARCHAR(200) NOT NULL,
    quest_type VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Quest participants (PCs in the quest, with their starting level frozen)
CREATE TABLE IF NOT EXISTS quest_participants (
    id SERIAL PRIMARY KEY,
    quest_id INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    starting_level INTEGER NOT NULL,
    starting_xp INTEGER NOT NULL,
    joined_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(quest_id, character_id)
);

-- Quest DMs (can have multiple DMs per quest)
CREATE TABLE IF NOT EXISTS quest_dms (
    id SERIAL PRIMARY KEY,
    quest_id INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(quest_id, user_id)
);

-- Quest monsters/encounters (for XP calculation)
CREATE TABLE IF NOT EXISTS quest_monsters (
    id SERIAL PRIMARY KEY,
    quest_id INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    monster_name VARCHAR(200),
    cr VARCHAR(10) NOT NULL,
    count INTEGER DEFAULT 1 CHECK (count > 0),
    added_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for quest tables
CREATE INDEX IF NOT EXISTS idx_quests_guild_id ON quests(guild_id);
CREATE INDEX IF NOT EXISTS idx_quests_status ON quests(status);
CREATE INDEX IF NOT EXISTS idx_quest_participants_quest_id ON quest_participants(quest_id);
CREATE INDEX IF NOT EXISTS idx_quest_participants_character_id ON quest_participants(character_id);
CREATE INDEX IF NOT EXISTS idx_quest_dms_quest_id ON quest_dms(quest_id);
CREATE INDEX IF NOT EXISTS idx_quest_dms_user_id ON quest_dms(user_id);
CREATE INDEX IF NOT EXISTS idx_quest_monsters_quest_id ON quest_monsters(quest_id);
