"""
Migration script to transfer data from xp.json to PostgreSQL database.

Usage:
  1. Ensure DATABASE_URL is set in your environment
  2. Ensure xp.json exists in the current directory
  3. Run: python migrate_to_postgres.py
"""
import json
import asyncio
import os
from database import Database

async def migrate():
    # Load JSON data
    try:
        with open('xp.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ xp.json not found. Nothing to migrate.")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Error reading xp.json: {e}")
        return

    # Initialize database
    db = Database()
    await db.connect()
    await db.initialize_schema()

    print("🔄 Starting migration from xp.json to PostgreSQL...\n")

    # Get GUILD_ID from environment
    guild_id = int(os.getenv("GUILD_ID", 0))
    if not guild_id:
        print("⚠️  GUILD_ID not set, using default guild ID 0")

    # Migrate guild configuration
    print("📝 Migrating guild configuration...")
    config_keys = ['rp_channels', 'hf_channels', 'char_per_rp', 'daily_rp_cap',
                   'hf_attempt_xp', 'hf_success_xp', 'daily_hf_cap']

    config_data = {}
    for key in config_keys:
        if key in data:
            config_data[key] = data[key]

    if config_data:
        await db.update_config(guild_id, **config_data)
        print(f"✅ Guild config migrated: {config_data}\n")

    # Migrate users and characters
    user_count = 0
    char_count = 0

    for user_id_str, user_data in data.items():
        # Skip non-user keys (config keys)
        if not isinstance(user_data, dict) or 'characters' not in user_data:
            continue

        try:
            user_id = int(user_id_str)
        except ValueError:
            print(f"⚠️  Skipping invalid user ID: {user_id_str}")
            continue

        print(f"👤 Migrating user {user_id}...")

        # Create user
        await db.ensure_user(user_id)

        # Set timezone
        if 'timezone' in user_data:
            await db.set_user_timezone(user_id, user_data['timezone'])

        # Set last XP reset date
        if 'last_xp_reset' in user_data and user_data['last_xp_reset']:
            try:
                from datetime import date
                reset_date = date.fromisoformat(user_data['last_xp_reset'])
                await db.update_last_xp_reset(user_id, reset_date)
            except ValueError:
                print(f"  ⚠️  Invalid date format for last_xp_reset: {user_data['last_xp_reset']}")

        user_count += 1

        # Migrate characters
        characters = user_data.get('characters', {})
        active_char_name = user_data.get('active')

        for char_name, char_data in characters.items():
            print(f"  📦 Creating character: {char_name}")

            # Create character
            char_id = await db.create_character(
                user_id,
                char_name,
                char_data.get('image_url')
            )

            # Update character with XP and daily stats
            xp = char_data.get('xp', 0)
            daily_xp = char_data.get('daily_xp', 0)
            daily_hf = char_data.get('daily_hf', 0)
            char_buffer = char_data.get('char_buffer', 0)

            if xp or daily_xp or daily_hf or char_buffer:
                await db.award_xp(
                    user_id,
                    char_name,
                    xp,  # Set total XP
                    daily_xp_delta=daily_xp - 0,  # Set current daily_xp
                    daily_hf_delta=daily_hf - 0,  # Set current daily_hf
                    char_buffer_delta=char_buffer - 0  # Set current buffer
                )

            char_count += 1

        # Set active character (do this after all characters are created)
        if active_char_name and active_char_name in characters:
            await db.set_active_character(user_id, active_char_name)
            print(f"  🟢 Set active character: {active_char_name}")

        print(f"✅ User {user_id} migrated with {len(characters)} characters\n")

    # Close database connection
    await db.close()

    print("=" * 50)
    print(f"✅ Migration complete!")
    print(f"   Users migrated: {user_count}")
    print(f"   Characters migrated: {char_count}")
    print("=" * 50)
    print("\n💡 Next steps:")
    print("  1. Verify the migration by connecting to your database")
    print("  2. Test the bot locally with the new database")
    print("  3. Create a backup of xp.json (just in case)")
    print("  4. Deploy to Fly.io\n")

if __name__ == "__main__":
    asyncio.run(migrate())
