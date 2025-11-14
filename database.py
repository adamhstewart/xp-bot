"""
Database layer for XP Bot using asyncpg
"""
import os
import logging
import asyncpg
from datetime import date
from typing import Optional, Dict, List, Tuple
from utils.exceptions import (
    DatabaseConnectionError,
    DatabaseTimeoutError,
    DatabaseError,
    CharacterNotFoundError,
    DuplicateCharacterError
)
from utils.retry import retry_on_db_error

logger = logging.getLogger('xp-bot.database')


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Initialize database connection pool"""
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            raise DatabaseConnectionError("DATABASE_URL environment variable not set")

        try:
            logger.debug(f"Connecting to database (pool size: 2-10)")
            self.pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connected successfully")
        except asyncpg.InvalidCatalogNameError as e:
            logger.error(f"Database does not exist: {e}")
            raise DatabaseConnectionError(f"Database does not exist: {e}") from e
        except asyncpg.InvalidPasswordError as e:
            logger.error(f"Invalid database credentials: {e}")
            raise DatabaseConnectionError(f"Invalid database credentials") from e
        except asyncpg.CannotConnectNowError as e:
            logger.error(f"Database is not accepting connections: {e}")
            raise DatabaseConnectionError(f"Database is not ready") from e
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise DatabaseConnectionError(f"Database connection failed: {e}") from e

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

    @retry_on_db_error(max_attempts=3, delay=1.0)
    async def initialize_schema(self):
        """Create tables if they don't exist"""
        try:
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            logger.debug(f"Loading schema from {schema_path}")

            with open(schema_path, 'r') as f:
                schema_sql = f.read()

            async with self.pool.acquire() as conn:
                await conn.execute(schema_sql)
            logger.info("Database schema initialized")
        except FileNotFoundError:
            logger.error(f"Schema file not found: {schema_path}")
            raise DatabaseError(f"Schema file not found") from None
        except asyncpg.PostgresError as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise DatabaseError(f"Failed to initialize database schema") from e
        except Exception as e:
            logger.error(f"Unexpected error initializing schema: {e}")
            raise DatabaseError(f"Database initialization failed") from e

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
                    INSERT INTO config (guild_id, rp_channels, survival_channels, char_per_rp,
                                       daily_rp_cap, character_creation_roles, xp_request_channel)
                    VALUES ($1, '{}', '{}', 240, 10, '{}', NULL)
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

    async def add_survival_channel(self, guild_id: int, channel_id: int):
        """Add channel to survival (prized species) tracking list"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE config
                SET survival_channels = array_append(survival_channels, $2),
                    updated_at = NOW()
                WHERE guild_id = $1 AND NOT ($2 = ANY(survival_channels))
            """, guild_id, channel_id)

    async def remove_survival_channel(self, guild_id: int, channel_id: int):
        """Remove channel from survival (prized species) tracking list"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE config
                SET survival_channels = array_remove(survival_channels, $2),
                    updated_at = NOW()
                WHERE guild_id = $1
            """, guild_id, channel_id)

    async def add_character_creation_role(self, guild_id: int, role_id: int):
        """Add role to character creation permissions"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE config
                SET character_creation_roles = array_append(character_creation_roles, $2),
                    updated_at = NOW()
                WHERE guild_id = $1 AND NOT ($2 = ANY(character_creation_roles))
            """, guild_id, role_id)

    async def remove_character_creation_role(self, guild_id: int, role_id: int):
        """Remove role from character creation permissions"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE config
                SET character_creation_roles = array_remove(character_creation_roles, $2),
                    updated_at = NOW()
                WHERE guild_id = $1
            """, guild_id, role_id)

    async def get_character_creation_roles(self, guild_id: int) -> list:
        """Get list of role IDs allowed to create characters"""
        config = await self.get_config(guild_id)
        return config.get('character_creation_roles', [])

    async def set_xp_request_channel(self, guild_id: int, channel_id: int):
        """Set the channel where XP requests are posted"""
        await self.update_config(guild_id, xp_request_channel=channel_id)

    async def get_xp_request_channel(self, guild_id: int) -> Optional[int]:
        """Get the XP request channel ID"""
        config = await self.get_config(guild_id)
        return config.get('xp_request_channel')

    async def get_log_channel(self) -> Optional[int]:
        """Get the log channel ID (XP request channel) for the first configured guild
        This is a helper method for code that doesn't have access to guild_id"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT xp_request_channel FROM config LIMIT 1"
            )
            return result

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

    @retry_on_db_error(max_attempts=2)
    async def create_character(self, user_id: int, name: str, image_url: Optional[str] = None, character_sheet_url: Optional[str] = None, starting_xp: int = 0) -> int:
        """Create a new character with optional starting XP, returns character ID"""
        await self.ensure_user(user_id)

        try:
            async with self.pool.acquire() as conn:
                char_id = await conn.fetchval("""
                    INSERT INTO characters (user_id, name, image_url, character_sheet_url, xp, daily_xp, char_buffer)
                    VALUES ($1, $2, $3, $4, $5, 0, 0)
                    RETURNING id
                """, user_id, name, image_url, character_sheet_url, starting_xp)

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
            raise DuplicateCharacterError(name, user_id) from None
        except asyncpg.PostgresError as e:
            logger.error(f"Database error creating character '{name}' for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create character") from e
        except Exception as e:
            logger.error(f"Unexpected error creating character '{name}' for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create character") from e

    async def delete_character(self, user_id: int, name: str) -> bool:
        """Delete a character permanently, returns True if deleted
        DEPRECATED: Use retire_character() instead for soft deletion"""
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

    async def retire_character(self, user_id: int, name: str) -> bool:
        """Retire a character (soft delete), returns True if retired
        Retired characters are hidden but can be restored"""
        async with self.pool.acquire() as conn:
            # Get character ID
            char = await conn.fetchrow(
                "SELECT id FROM characters WHERE user_id = $1 AND name = $2 AND retired = FALSE",
                user_id, name
            )

            if not char:
                return False

            # Mark as retired and clear if it's the active character
            await conn.execute("""
                UPDATE characters
                SET retired = TRUE, updated_at = NOW()
                WHERE id = $1
            """, char['id'])

            # Clear active_character_id if this was the active character
            await conn.execute("""
                UPDATE users
                SET active_character_id = NULL, updated_at = NOW()
                WHERE user_id = $1 AND active_character_id = $2
            """, user_id, char['id'])

            logger.info(f"Retired character '{name}' (ID: {char['id']}) for user {user_id}")
            return True

    async def restore_character(self, user_id: int, name: str) -> bool:
        """Restore a retired character, returns True if restored"""
        async with self.pool.acquire() as conn:
            # Get retired character
            char = await conn.fetchrow(
                "SELECT id FROM characters WHERE user_id = $1 AND name = $2 AND retired = TRUE",
                user_id, name
            )

            if not char:
                return False

            # Unmark as retired
            await conn.execute("""
                UPDATE characters
                SET retired = FALSE, updated_at = NOW()
                WHERE id = $1
            """, char['id'])

            logger.info(f"Restored character '{name}' (ID: {char['id']}) for user {user_id}")
            return True

    async def purge_user(self, user_id: int) -> bool:
        """Permanently delete a user and all their characters (for GDPR compliance)
        Returns True if user existed and was deleted"""
        async with self.pool.acquire() as conn:
            # Check if user exists
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE user_id = $1",
                user_id
            )

            if not user:
                return False

            # Delete user (CASCADE will delete all characters and related data)
            await conn.execute(
                "DELETE FROM users WHERE user_id = $1",
                user_id
            )

            logger.warning(f"PURGED user {user_id} and all their characters from database")
            return True

    async def get_character(self, user_id: int, name: str, include_retired: bool = False) -> Optional[Dict]:
        """Get character by name (excludes retired by default)"""
        async with self.pool.acquire() as conn:
            if include_retired:
                char = await conn.fetchrow(
                    "SELECT * FROM characters WHERE user_id = $1 AND name = $2",
                    user_id, name
                )
            else:
                char = await conn.fetchrow(
                    "SELECT * FROM characters WHERE user_id = $1 AND name = $2 AND retired = FALSE",
                    user_id, name
                )
            return dict(char) if char else None

    async def get_active_character(self, user_id: int) -> Optional[Dict]:
        """Get user's active character (excludes retired)"""
        async with self.pool.acquire() as conn:
            char = await conn.fetchrow("""
                SELECT c.* FROM characters c
                JOIN users u ON u.active_character_id = c.id
                WHERE u.user_id = $1 AND c.retired = FALSE
            """, user_id)
            return dict(char) if char else None

    async def set_active_character(self, user_id: int, name: str) -> bool:
        """Set user's active character by name (cannot set retired characters as active)"""
        async with self.pool.acquire() as conn:
            # Get character ID (only non-retired)
            char = await conn.fetchrow(
                "SELECT id FROM characters WHERE user_id = $1 AND name = $2 AND retired = FALSE",
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

    async def list_characters(self, user_id: int, include_retired: bool = False) -> List[Dict]:
        """List all characters for a user (excludes retired by default)"""
        async with self.pool.acquire() as conn:
            if include_retired:
                chars = await conn.fetch(
                    "SELECT * FROM characters WHERE user_id = $1 ORDER BY created_at",
                    user_id
                )
            else:
                chars = await conn.fetch(
                    "SELECT * FROM characters WHERE user_id = $1 AND retired = FALSE ORDER BY created_at",
                    user_id
                )
            return [dict(char) for char in chars]

    async def get_all_character_names(self, user_id: int, include_retired: bool = False) -> List[str]:
        """Get list of character names for a user (excludes retired by default)"""
        async with self.pool.acquire() as conn:
            if include_retired:
                names = await conn.fetch(
                    "SELECT name FROM characters WHERE user_id = $1",
                    user_id
                )
            else:
                names = await conn.fetch(
                    "SELECT name FROM characters WHERE user_id = $1 AND retired = FALSE",
                    user_id
                )
            return [row['name'] for row in names]

    async def find_character_by_name_any_user(self, name: str, include_retired: bool = False) -> Optional[Tuple[int, Dict]]:
        """Find character by name across all users (for HF tracking)
        Returns (user_id, character_dict) or None
        DEPRECATED: Use find_all_characters_by_name() for collision-safe lookups"""
        async with self.pool.acquire() as conn:
            if include_retired:
                char = await conn.fetchrow(
                    "SELECT * FROM characters WHERE name = $1 LIMIT 1",
                    name
                )
            else:
                char = await conn.fetchrow(
                    "SELECT * FROM characters WHERE name = $1 AND retired = FALSE LIMIT 1",
                    name
                )
            if char:
                return (char['user_id'], dict(char))
            return None

    async def find_all_characters_by_name(self, name: str, include_retired: bool = False) -> List[Tuple[int, Dict]]:
        """Find all characters with given name across all users (for HF tracking)
        Returns list of (user_id, character_dict) tuples (excludes retired by default)"""
        async with self.pool.acquire() as conn:
            if include_retired:
                chars = await conn.fetch(
                    "SELECT * FROM characters WHERE name = $1",
                    name
                )
            else:
                chars = await conn.fetch(
                    "SELECT * FROM characters WHERE name = $1 AND retired = FALSE",
                    name
                )
            return [(char['user_id'], dict(char)) for char in chars]

    async def search_all_character_names(self, search: str = "", limit: int = 25, include_retired: bool = False) -> List[str]:
        """Search for character names across all users (for autocomplete, excludes retired by default)
        Returns list of character names matching search term"""
        async with self.pool.acquire() as conn:
            if include_retired:
                if search:
                    chars = await conn.fetch(
                        "SELECT DISTINCT name FROM characters WHERE LOWER(name) LIKE LOWER($1) ORDER BY name LIMIT $2",
                        f"%{search}%", limit
                    )
                else:
                    chars = await conn.fetch(
                        "SELECT DISTINCT name FROM characters ORDER BY updated_at DESC LIMIT $1",
                        limit
                    )
            else:
                if search:
                    chars = await conn.fetch(
                        "SELECT DISTINCT name FROM characters WHERE LOWER(name) LIKE LOWER($1) AND retired = FALSE ORDER BY name LIMIT $2",
                        f"%{search}%", limit
                    )
                else:
                    chars = await conn.fetch(
                        "SELECT DISTINCT name FROM characters WHERE retired = FALSE ORDER BY updated_at DESC LIMIT $1",
                        limit
                    )
            return [row['name'] for row in chars]

    @retry_on_db_error(max_attempts=3)
    async def award_xp(self, user_id: int, char_name: str, xp_amount: int,
                       daily_xp_delta: int = 0, char_buffer_delta: int = 0) -> dict:
        """Award XP to a character and update daily counters
        Returns dict with: old_xp, new_xp, old_level, new_level, leveled_up"""
        try:
            async with self.pool.acquire() as conn:
                # Get old XP first
                old_char = await conn.fetchrow("""
                    SELECT xp FROM characters
                    WHERE user_id = $1 AND name = $2
                """, user_id, char_name)

                old_xp = old_char['xp'] if old_char else 0

                # Update XP
                result = await conn.execute("""
                    UPDATE characters
                    SET xp = xp + $3,
                        daily_xp = daily_xp + $4,
                        char_buffer = char_buffer + $5,
                        updated_at = NOW()
                    WHERE user_id = $1 AND name = $2
                """, user_id, char_name, xp_amount, daily_xp_delta, char_buffer_delta)

                # Get new XP
                new_char = await conn.fetchrow("""
                    SELECT xp FROM characters
                    WHERE user_id = $1 AND name = $2
                """, user_id, char_name)

                new_xp = new_char['xp'] if new_char else old_xp

                # Calculate levels
                from utils.xp import get_level_and_progress
                old_level, _, _ = get_level_and_progress(old_xp)
                new_level, _, _ = get_level_and_progress(new_xp)

                leveled_up = new_level > old_level

                if xp_amount > 0:
                    logger.debug(f"Awarded {xp_amount} XP to '{char_name}' (user {user_id}) - Level {old_level} -> {new_level}")

                return {
                    'old_xp': old_xp,
                    'new_xp': new_xp,
                    'old_level': old_level,
                    'new_level': new_level,
                    'leveled_up': leveled_up
                }
        except asyncpg.PostgresError as e:
            logger.error(f"Database error awarding XP to '{char_name}' for user {user_id}: {e}")
            raise DatabaseError(f"Failed to award XP") from e
        except Exception as e:
            logger.error(f"Unexpected error awarding XP to '{char_name}' for user {user_id}: {e}")
            raise DatabaseError(f"Failed to award XP") from e

    async def reset_daily_caps(self, user_id: int):
        """Reset daily XP caps for all user's characters"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE characters
                SET daily_xp = 0,
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

    async def log_xp_grant(self, character_id: int, granted_by_user_id: int, amount: int, memo: Optional[str] = None):
        """Log an XP grant for audit trail"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO xp_grants (character_id, granted_by_user_id, amount, memo)
                VALUES ($1, $2, $3, $4)
            """, character_id, granted_by_user_id, amount, memo)

    async def update_character(self, user_id: int, old_name: str, new_name: Optional[str] = None,
                              image_url: Optional[str] = None, character_sheet_url: Optional[str] = None) -> bool:
        """Update character details (name, image_url, character_sheet_url)
        Returns True if successful, False if character not found
        """
        try:
            async with self.pool.acquire() as conn:
                # Get the character first to check if it exists
                char = await conn.fetchrow(
                    "SELECT id FROM characters WHERE user_id = $1 AND name = $2",
                    user_id, old_name
                )

                if not char:
                    return False

                # Build dynamic update based on what's provided
                updates = []
                params = [user_id, old_name]
                param_idx = 3

                if new_name is not None:
                    updates.append(f"name = ${param_idx}")
                    params.append(new_name)
                    param_idx += 1

                if image_url is not None:
                    updates.append(f"image_url = ${param_idx}")
                    params.append(image_url)
                    param_idx += 1

                if character_sheet_url is not None:
                    updates.append(f"character_sheet_url = ${param_idx}")
                    params.append(character_sheet_url)
                    param_idx += 1

                # Always update timestamp
                updates.append("updated_at = NOW()")

                if len(updates) == 1:  # Only timestamp, nothing to update
                    return True

                query = f"""
                    UPDATE characters
                    SET {', '.join(updates)}
                    WHERE user_id = $1 AND name = $2
                """

                await conn.execute(query, *params)
                logger.info(f"Updated character '{old_name}' for user {user_id}")
                return True

        except asyncpg.UniqueViolationError:
            logger.warning(f"Cannot rename '{old_name}' to '{new_name}' - name already exists for user {user_id}")
            raise DuplicateCharacterError(new_name, user_id) from None
        except asyncpg.PostgresError as e:
            logger.error(f"Database error updating character '{old_name}' for user {user_id}: {e}")
            raise DatabaseError(f"Failed to update character") from e

    # ==================== QUEST METHODS ====================

    async def create_quest(self, guild_id: int, name: str, quest_type: str,
                          start_date: date, primary_dm_user_id: int) -> int:
        """Create a new quest and return its ID"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Create quest
                quest_id = await conn.fetchval("""
                    INSERT INTO quests (guild_id, name, quest_type, start_date, status)
                    VALUES ($1, $2, $3, $4, 'active')
                    RETURNING id
                """, guild_id, name, quest_type, start_date)

                # Add primary DM
                await conn.execute("""
                    INSERT INTO quest_dms (quest_id, user_id, is_primary)
                    VALUES ($1, $2, TRUE)
                """, quest_id, primary_dm_user_id)

                logger.info(f"Created quest '{name}' (ID: {quest_id}) for guild {guild_id}")
                return quest_id

    async def add_quest_participant(self, quest_id: int, character_id: int,
                                   starting_level: int, starting_xp: int):
        """Add a PC to a quest with their starting level/XP frozen"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO quest_participants (quest_id, character_id, starting_level, starting_xp)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (quest_id, character_id) DO NOTHING
            """, quest_id, character_id, starting_level, starting_xp)

    async def add_quest_dm(self, quest_id: int, user_id: int, is_primary: bool = False):
        """Add a DM to a quest"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO quest_dms (quest_id, user_id, is_primary)
                VALUES ($1, $2, $3)
                ON CONFLICT (quest_id, user_id) DO NOTHING
            """, quest_id, user_id, is_primary)

    async def get_quest(self, quest_id: int) -> Optional[Dict]:
        """Get quest details by ID"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM quests WHERE id = $1
            """, quest_id)
            return dict(result) if result else None

    async def get_active_quests(self, guild_id: int) -> List[Dict]:
        """Get all active quests for a guild"""
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT * FROM quests
                WHERE guild_id = $1 AND status = 'active'
                ORDER BY start_date DESC, created_at DESC
            """, guild_id)
            return [dict(r) for r in results]

    async def get_quest_participants(self, quest_id: int) -> List[Dict]:
        """Get all participants (PCs) in a quest with character details"""
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT qp.*, c.name as character_name, c.user_id
                FROM quest_participants qp
                JOIN characters c ON qp.character_id = c.id
                WHERE qp.quest_id = $1
                ORDER BY qp.joined_at
            """, quest_id)
            return [dict(r) for r in results]

    async def get_quest_dms(self, quest_id: int) -> List[Dict]:
        """Get all DMs for a quest"""
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT * FROM quest_dms
                WHERE quest_id = $1
                ORDER BY is_primary DESC, joined_at
            """, quest_id)
            return [dict(r) for r in results]

    async def add_quest_monster(self, quest_id: int, cr: str,
                               monster_name: str = None, count: int = 1):
        """Add a monster/encounter to a quest"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO quest_monsters (quest_id, monster_name, cr, count)
                VALUES ($1, $2, $3, $4)
            """, quest_id, monster_name, cr, count)

    async def get_quest_monsters(self, quest_id: int) -> List[Dict]:
        """Get all monsters/encounters for a quest"""
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT * FROM quest_monsters
                WHERE quest_id = $1
                ORDER BY added_at
            """, quest_id)
            return [dict(r) for r in results]

    async def complete_quest(self, quest_id: int, end_date: date) -> bool:
        """Mark a quest as completed"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE quests
                SET status = 'completed', end_date = $2, updated_at = NOW()
                WHERE id = $1 AND status = 'active'
            """, quest_id, end_date)
            # Check if any rows were updated
            return result.split()[-1] != '0'

    async def get_character_active_quests(self, character_id: int) -> List[Dict]:
        """Get all active quests a character is participating in"""
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT q.* FROM quests q
                JOIN quest_participants qp ON q.id = qp.quest_id
                WHERE qp.character_id = $1 AND q.status = 'active'
                ORDER BY q.start_date DESC
            """, character_id)
            return [dict(r) for r in results]

    async def search_active_quests(self, guild_id: int, search_term: str, limit: int = 25) -> List[str]:
        """Search active quest names for autocomplete"""
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT name FROM quests
                WHERE guild_id = $1 AND status = 'active'
                AND LOWER(name) LIKE LOWER($2)
                ORDER BY start_date DESC
                LIMIT $3
            """, guild_id, f"%{search_term}%", limit)
            return [r['name'] for r in results]

    async def get_quest_by_name(self, guild_id: int, name: str) -> Optional[Dict]:
        """Get active quest by exact name match"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM quests
                WHERE guild_id = $1 AND name = $2 AND status = 'active'
            """, guild_id, name)
            return dict(result) if result else None

    async def get_quest_by_name_any_status(self, guild_id: int, name: str) -> Optional[Dict]:
        """Get quest by exact name match (any status)"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM quests
                WHERE guild_id = $1 AND name = $2
                ORDER BY created_at DESC
                LIMIT 1
            """, guild_id, name)
            return dict(result) if result else None

    async def search_completed_quests(self, guild_id: int, search_term: str, limit: int = 25) -> List[str]:
        """Search completed quest names for autocomplete"""
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT name FROM quests
                WHERE guild_id = $1 AND status = 'completed'
                AND LOWER(name) LIKE LOWER($2)
                ORDER BY end_date DESC
                LIMIT $3
            """, guild_id, f"%{search_term}%", limit)
            return [r['name'] for r in results]

    async def get_completed_quest_by_name(self, guild_id: int, name: str) -> Optional[Dict]:
        """Get completed quest by exact name match"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM quests
                WHERE guild_id = $1 AND name = $2 AND status = 'completed'
                ORDER BY end_date DESC
                LIMIT 1
            """, guild_id, name)
            return dict(result) if result else None
