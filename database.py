"""
Database layer for XP Bot using asyncpg
"""
import os
import logging
import asyncpg
from datetime import date
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger('xp-bot.database')


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Initialize database connection pool"""
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            raise ValueError("DATABASE_URL environment variable not set")

        logger.debug(f"Connecting to database (pool size: 2-10)")
        self.pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        logger.info("Database connected successfully")

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

    async def initialize_schema(self):
        """Create tables if they don't exist"""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        logger.debug(f"Loading schema from {schema_path}")

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)
        logger.info("Database schema initialized")

    # ==================== CONFIG METHODS ====================

    async def get_config(self, guild_id: int) -> Dict:
        """Get guild configuration, create if doesn't exist"""
        async with self.pool.acquire() as conn:
            config = await conn.fetchrow(
                "SELECT * FROM config WHERE guild_id = $1",
                guild_id
            )

            if not config:
                # Create default config
                config = await conn.fetchrow("""
                    INSERT INTO config (guild_id, rp_channels, hf_channels, char_per_rp,
                                       daily_rp_cap, hf_attempt_xp, hf_success_xp, daily_hf_cap)
                    VALUES ($1, '{}', '{}', 240, 10, 1, 5, 10)
                    RETURNING *
                """, guild_id)

            return dict(config)

    async def update_config(self, guild_id: int, **kwargs):
        """Update guild configuration"""
        # Build dynamic UPDATE query
        set_clauses = []
        values = [guild_id]
        param_index = 2

        for key, value in kwargs.items():
            set_clauses.append(f"{key} = ${param_index}")
            values.append(value)
            param_index += 1

        set_clauses.append(f"updated_at = NOW()")

        query = f"UPDATE config SET {', '.join(set_clauses)} WHERE guild_id = $1"

        async with self.pool.acquire() as conn:
            await conn.execute(query, *values)

    async def add_rp_channel(self, guild_id: int, channel_id: int):
        """Add channel to RP tracking list"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE config
                SET rp_channels = array_append(rp_channels, $2),
                    updated_at = NOW()
                WHERE guild_id = $1 AND NOT ($2 = ANY(rp_channels))
            """, guild_id, channel_id)

    async def remove_rp_channel(self, guild_id: int, channel_id: int):
        """Remove channel from RP tracking list"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE config
                SET rp_channels = array_remove(rp_channels, $2),
                    updated_at = NOW()
                WHERE guild_id = $1
            """, guild_id, channel_id)

    async def add_hf_channel(self, guild_id: int, channel_id: int):
        """Add channel to HF tracking list"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE config
                SET hf_channels = array_append(hf_channels, $2),
                    updated_at = NOW()
                WHERE guild_id = $1 AND NOT ($2 = ANY(hf_channels))
            """, guild_id, channel_id)

    async def remove_hf_channel(self, guild_id: int, channel_id: int):
        """Remove channel from HF tracking list"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE config
                SET hf_channels = array_remove(hf_channels, $2),
                    updated_at = NOW()
                WHERE guild_id = $1
            """, guild_id, channel_id)

    # ==================== USER METHODS ====================

    async def ensure_user(self, user_id: int) -> Dict:
        """Get or create user, returns user data with active character info"""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1",
                user_id
            )

            if not user:
                # Create new user
                user = await conn.fetchrow("""
                    INSERT INTO users (user_id, timezone, last_xp_reset)
                    VALUES ($1, 'UTC', CURRENT_DATE)
                    RETURNING *
                """, user_id)

            return dict(user)

    async def get_user_timezone(self, user_id: int) -> str:
        """Get user's timezone"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT timezone FROM users WHERE user_id = $1",
                user_id
            )
            return result or 'UTC'

    async def set_user_timezone(self, user_id: int, timezone: str):
        """Set user's timezone"""
        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET timezone = $2, updated_at = NOW()
                WHERE user_id = $1
            """, user_id, timezone)

    async def get_last_xp_reset(self, user_id: int) -> Optional[date]:
        """Get user's last XP reset date"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT last_xp_reset FROM users WHERE user_id = $1",
                user_id
            )

    async def update_last_xp_reset(self, user_id: int, reset_date: date):
        """Update user's last XP reset date"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET last_xp_reset = $2, updated_at = NOW()
                WHERE user_id = $1
            """, user_id, reset_date)

    # ==================== CHARACTER METHODS ====================

    async def create_character(self, user_id: int, name: str, image_url: Optional[str] = None) -> int:
        """Create a new character, returns character ID"""
        await self.ensure_user(user_id)

        try:
            async with self.pool.acquire() as conn:
                char_id = await conn.fetchval("""
                    INSERT INTO characters (user_id, name, image_url, xp, daily_xp, daily_hf, char_buffer)
                    VALUES ($1, $2, $3, 0, 0, 0, 0)
                    RETURNING id
                """, user_id, name, image_url)

                # Set as active character if user has no active character
                await conn.execute("""
                    UPDATE users
                    SET active_character_id = $2, updated_at = NOW()
                    WHERE user_id = $1 AND active_character_id IS NULL
                """, user_id, char_id)

                logger.info(f"Created character '{name}' (ID: {char_id}) for user {user_id}")
                return char_id
        except asyncpg.UniqueViolationError:
            logger.warning(f"Duplicate character name '{name}' for user {user_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to create character '{name}' for user {user_id}: {e}")
            raise

    async def delete_character(self, user_id: int, name: str) -> bool:
        """Delete a character, returns True if deleted"""
        async with self.pool.acquire() as conn:
            # Get character ID first
            char = await conn.fetchrow(
                "SELECT id FROM characters WHERE user_id = $1 AND name = $2",
                user_id, name
            )

            if not char:
                return False

            # Delete character (CASCADE will handle active_character_id via SET NULL)
            await conn.execute(
                "DELETE FROM characters WHERE id = $1",
                char['id']
            )

            return True

    async def get_character(self, user_id: int, name: str) -> Optional[Dict]:
        """Get character by name"""
        async with self.pool.acquire() as conn:
            char = await conn.fetchrow(
                "SELECT * FROM characters WHERE user_id = $1 AND name = $2",
                user_id, name
            )
            return dict(char) if char else None

    async def get_active_character(self, user_id: int) -> Optional[Dict]:
        """Get user's active character"""
        async with self.pool.acquire() as conn:
            char = await conn.fetchrow("""
                SELECT c.* FROM characters c
                JOIN users u ON u.active_character_id = c.id
                WHERE u.user_id = $1
            """, user_id)
            return dict(char) if char else None

    async def set_active_character(self, user_id: int, name: str) -> bool:
        """Set user's active character by name"""
        async with self.pool.acquire() as conn:
            # Get character ID
            char = await conn.fetchrow(
                "SELECT id FROM characters WHERE user_id = $1 AND name = $2",
                user_id, name
            )

            if not char:
                return False

            # Update user's active character
            await conn.execute("""
                UPDATE users
                SET active_character_id = $2, updated_at = NOW()
                WHERE user_id = $1
            """, user_id, char['id'])

            return True

    async def list_characters(self, user_id: int) -> List[Dict]:
        """List all characters for a user"""
        async with self.pool.acquire() as conn:
            chars = await conn.fetch(
                "SELECT * FROM characters WHERE user_id = $1 ORDER BY created_at",
                user_id
            )
            return [dict(char) for char in chars]

    async def get_all_character_names(self, user_id: int) -> List[str]:
        """Get list of character names for a user (for fuzzy matching)"""
        async with self.pool.acquire() as conn:
            names = await conn.fetch(
                "SELECT name FROM characters WHERE user_id = $1",
                user_id
            )
            return [row['name'] for row in names]

    async def find_character_by_name_any_user(self, name: str) -> Optional[Tuple[int, Dict]]:
        """Find character by name across all users (for HF tracking)
        Returns (user_id, character_dict) or None"""
        async with self.pool.acquire() as conn:
            char = await conn.fetchrow(
                "SELECT * FROM characters WHERE name = $1 LIMIT 1",
                name
            )
            if char:
                return (char['user_id'], dict(char))
            return None

    async def award_xp(self, user_id: int, char_name: str, xp_amount: int,
                       daily_xp_delta: int = 0, daily_hf_delta: int = 0,
                       char_buffer_delta: int = 0):
        """Award XP to a character and update daily counters"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    UPDATE characters
                    SET xp = xp + $3,
                        daily_xp = daily_xp + $4,
                        daily_hf = daily_hf + $5,
                        char_buffer = char_buffer + $6,
                        updated_at = NOW()
                    WHERE user_id = $1 AND name = $2
                """, user_id, char_name, xp_amount, daily_xp_delta, daily_hf_delta, char_buffer_delta)

                if xp_amount > 0:
                    logger.debug(f"Awarded {xp_amount} XP to '{char_name}' (user {user_id})")
        except Exception as e:
            logger.error(f"Failed to award XP to '{char_name}' for user {user_id}: {e}")
            raise

    async def reset_daily_caps(self, user_id: int):
        """Reset daily XP caps for all user's characters"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE characters
                SET daily_xp = 0,
                    daily_hf = 0,
                    char_buffer = 0,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id)

    async def update_character_buffer(self, user_id: int, char_name: str, new_buffer: int):
        """Update character's buffer (for RP XP accumulation)"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE characters
                SET char_buffer = $3, updated_at = NOW()
                WHERE user_id = $1 AND name = $2
            """, user_id, char_name, new_buffer)
