-- Quest Tracking System Migration
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

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_quests_guild_id ON quests(guild_id);
CREATE INDEX IF NOT EXISTS idx_quests_status ON quests(status);
CREATE INDEX IF NOT EXISTS idx_quest_participants_quest_id ON quest_participants(quest_id);
CREATE INDEX IF NOT EXISTS idx_quest_participants_character_id ON quest_participants(character_id);
CREATE INDEX IF NOT EXISTS idx_quest_dms_quest_id ON quest_dms(quest_id);
CREATE INDEX IF NOT EXISTS idx_quest_dms_user_id ON quest_dms(user_id);
CREATE INDEX IF NOT EXISTS idx_quest_monsters_quest_id ON quest_monsters(quest_id);
