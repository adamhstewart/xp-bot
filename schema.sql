-- XP Bot PostgreSQL Schema

-- Guild configuration (global settings)
CREATE TABLE IF NOT EXISTS config (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    rp_channels BIGINT[] DEFAULT '{}',
    hf_channels BIGINT[] DEFAULT '{}',
    char_per_rp INTEGER DEFAULT 240,
    daily_rp_cap INTEGER DEFAULT 10,
    hf_attempt_xp INTEGER DEFAULT 1,
    hf_success_xp INTEGER DEFAULT 5,
    daily_hf_cap INTEGER DEFAULT 10,
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
    daily_hf INTEGER DEFAULT 0,
    char_buffer INTEGER DEFAULT 0,
    image_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Add foreign key for active character (must be after characters table exists)
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_active_character;
ALTER TABLE users
    ADD CONSTRAINT fk_active_character
    FOREIGN KEY (active_character_id)
    REFERENCES characters(id) ON DELETE SET NULL;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_characters_user_id ON characters(user_id);
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
CREATE INDEX IF NOT EXISTS idx_users_last_reset ON users(last_xp_reset);
