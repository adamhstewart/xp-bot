# Local Development Guide

Quick start guide for running XP Bot locally with PostgreSQL.

## Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (recommended) OR PostgreSQL installed locally
- **Discord Bot Token** (from [Discord Developer Portal](https://discord.com/developers/applications))
- **Discord Server** with a Guild ID

## Quick Start (Docker Compose - Recommended)

### 1. Clone and Setup Environment

```bash
# Navigate to project directory
cd xp-bot

# Create .env file with your credentials
cat > .env << EOF
DISCORD_BOT_TOKEN=your_token_here
GUILD_ID=your_guild_id_here
ENV=dev
EOF
```

### 2. Start Services

```bash
# Start PostgreSQL and the bot
docker-compose up

# Or run in background
docker-compose up -d
```

That's it! The bot should now be online and connected to the local PostgreSQL database.

### 3. Migrate Existing Data (Optional)

If you have an existing `xp.json` file:

```bash
# In a new terminal (while docker-compose is running)
export DATABASE_URL="postgresql://xpbot:xpbot_dev_password@localhost:5432/xpbot"
python migrate_to_postgres.py
```

### 4. Stop Services

```bash
# Stop everything
docker-compose down

# Stop and remove volumes (deletes database data)
docker-compose down -v
```

---

## Alternative: Manual Setup (Without Docker)

### 1. Install PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Download from [postgresql.org](https://www.postgresql.org/download/windows/)

### 2. Create Database

```bash
# Connect to PostgreSQL
psql postgres

# Create database and user
CREATE DATABASE xpbot;
CREATE USER xpbot WITH PASSWORD 'dev_password';
GRANT ALL PRIVILEGES ON DATABASE xpbot TO xpbot;
\q
```

### 3. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Create .env file
cat > .env << EOF
DISCORD_BOT_TOKEN=your_token_here
GUILD_ID=your_guild_id_here
DATABASE_URL=postgresql://xpbot:dev_password@localhost:5432/xpbot
ENV=dev
EOF
```

### 5. Run Migration (Optional)

```bash
# If you have existing xp.json
python migrate_to_postgres.py
```

### 6. Start the Bot

```bash
python bot.py
```

---

## Development Workflow

### Making Code Changes

With Docker Compose, the bot automatically restarts when you modify Python files thanks to `watchmedo`:

```bash
# Edit bot.py or database.py
# Save the file
# Bot automatically restarts - check logs in terminal
```

**Without auto-restart**, manually restart:
```bash
# Stop bot (Ctrl+C)
# Start again
python bot.py
```

### Database Management

#### Connect to Database Console

**With Docker:**
```bash
docker-compose exec postgres psql -U xpbot -d xpbot
```

**Without Docker:**
```bash
psql -U xpbot -d xpbot
```

#### Useful SQL Queries

```sql
-- View all users
SELECT user_id, timezone, last_xp_reset FROM users;

-- View all characters with XP
SELECT u.user_id, c.name, c.xp, c.daily_xp, c.daily_hf
FROM characters c
JOIN users u ON c.user_id = u.user_id
ORDER BY c.xp DESC;

-- View guild configuration
SELECT * FROM config;

-- Count total characters
SELECT COUNT(*) FROM characters;

-- Find top 10 characters by XP
SELECT name, xp FROM characters ORDER BY xp DESC LIMIT 10;

-- Delete all data (CAREFUL!)
TRUNCATE users, characters, config CASCADE;
```

#### Reset Database Schema

```bash
# With Docker
docker-compose down -v  # Remove volumes
docker-compose up -d    # Recreate everything

# Without Docker
dropdb xpbot
createdb xpbot
python bot.py  # Schema auto-creates on startup
```

### View Logs

**With Docker:**
```bash
# Follow logs
docker-compose logs -f xp-bot

# View PostgreSQL logs
docker-compose logs -f postgres

# Both
docker-compose logs -f
```

**Without Docker:**
Logs print to your terminal where you ran `python bot.py`

---

## Testing Commands

### 1. Create Test Character

In Discord:
```
/xp_create char_name:TestChar image_url:https://example.com/image.png
```

### 2. View Character

```
/xp
```

### 3. Test RP XP Tracking

```
# First, add a channel for RP tracking (admin only)
/xp_add_rp_channel channel:#rp-channel

# Send messages in that channel
# Each 240 characters = 1 XP (default)
```

### 4. Test Character Listing

```
/xp_list
```

### 5. Set Active Character

```
/xp_active char_name:TestChar
```

### 6. Grant XP (Admin)

```
/xp_grant character_name:TestChar amount:100
```

### 7. View Configuration (Admin)

```
!xpsettings
```

---

## Common Development Tasks

### Add a New Database Field

1. **Update schema.sql:**
```sql
ALTER TABLE characters ADD COLUMN new_field VARCHAR(100);
```

2. **Update database.py:**
```python
async def get_new_field(self, user_id: int):
    async with self.pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT new_field FROM characters WHERE user_id = $1",
            user_id
        )
```

3. **Update bot.py** to use the new field

4. **Recreate database** (development only):
```bash
docker-compose down -v
docker-compose up
```

### Debug Database Queries

Enable query logging in `database.py`:

```python
# In database.py, add to connect() method:
await self.pool.execute("SET log_statement = 'all';")
```

Or watch PostgreSQL logs:
```bash
docker-compose logs -f postgres | grep STATEMENT
```

### Test Migration Script

```bash
# Dry run (doesn't modify database, just shows what would happen)
# Edit migrate_to_postgres.py to add a --dry-run flag

# Or test against a separate database
export DATABASE_URL="postgresql://xpbot:dev_password@localhost:5432/xpbot_test"
python migrate_to_postgres.py
```

---

## Environment Variables Reference

Create a `.env` file in the project root:

```bash
# Required
DISCORD_BOT_TOKEN=your_discord_bot_token_here
GUILD_ID=your_discord_server_id

# Optional (defaults provided)
DATABASE_URL=postgresql://xpbot:xpbot_dev_password@localhost:5432/xpbot
ENV=dev
PORT=8080
```

### How to Get These Values

**DISCORD_BOT_TOKEN:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create/select your application
3. Go to "Bot" section
4. Click "Reset Token" → Copy the token
5. **Keep this secret!** Never commit to git

**GUILD_ID:**
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click your server → Copy Server ID

---

## Troubleshooting

### "DATABASE_URL environment variable not set"

**Solution:**
```bash
# Add to .env file
DATABASE_URL=postgresql://xpbot:xpbot_dev_password@localhost:5432/xpbot

# Or export directly
export DATABASE_URL="postgresql://xpbot:xpbot_dev_password@localhost:5432/xpbot"
```

### "Connection refused" / "Can't connect to database"

**With Docker:**
```bash
# Check if postgres is running
docker-compose ps

# Restart if needed
docker-compose restart postgres
```

**Without Docker:**
```bash
# Check PostgreSQL status
brew services list  # macOS
sudo systemctl status postgresql  # Linux

# Start if stopped
brew services start postgresql@15  # macOS
sudo systemctl start postgresql  # Linux
```

### "relation does not exist" / "table not found"

The schema wasn't created. Restart the bot - it auto-creates tables on startup:

```bash
docker-compose restart xp-bot
# Or
python bot.py
```

### "discord.py not installed" or import errors

```bash
# Reinstall dependencies
pip install -r requirements.txt

# Or with Docker
docker-compose build --no-cache
docker-compose up
```

### Bot not responding to commands

1. **Check bot is online:**
   - Look for `✅ xp-bot is online.` in logs
   - Check Discord - bot should show as online

2. **Check commands synced:**
   - Look for `✅ Synced X slash commands to dev guild` in logs
   - In Discord, type `/xp` - you should see autocomplete

3. **Sync manually:**
   ```
   /xp_sync
   ```

4. **Check permissions:**
   - Bot needs `applications.commands` scope
   - Reinvite bot with correct permissions

### Bot keeps restarting / crash loop

**With Docker:**
```bash
# View error logs
docker-compose logs xp-bot

# Common issues:
# - DATABASE_URL not set
# - DISCORD_BOT_TOKEN invalid
# - Syntax error in code
```

**Fix:**
1. Check logs for error message
2. Verify .env file has correct values
3. Test database connection separately

### Changes not taking effect

**With Docker:**
```bash
# Rebuild image
docker-compose build
docker-compose up

# Or force recreate
docker-compose up --force-recreate
```

**Without Docker:**
- Restart `python bot.py`
- Check you're editing the right file
- Verify virtual environment is activated

---

## Pro Tips

### Use a Database GUI

**Recommended tools:**
- [pgAdmin](https://www.pgadmin.org/) - Full-featured
- [DBeaver](https://dbeaver.io/) - Cross-platform
- [TablePlus](https://tableplus.com/) - macOS/Windows (paid)
- [Postico](https://eggerapps.at/postico/) - macOS only

**Connection details:**
- Host: `localhost`
- Port: `5432`
- Database: `xpbot`
- User: `xpbot`
- Password: `xpbot_dev_password` (Docker) or your password

### VS Code Extensions

Useful extensions for development:
- **Python** - IntelliSense and debugging
- **PostgreSQL** - SQL syntax highlighting
- **Docker** - Manage containers from VS Code
- **Thunder Client** - Test APIs (if you add any)

### Hot Reload Setup

The Docker Compose setup uses `watchmedo` for auto-restart:

```yaml
# In docker-compose.yml
command: watchmedo auto-restart -d . -p '*.py' -- python bot.py
```

This watches for changes to `.py` files and restarts automatically.

### Create Test Data Quickly

```sql
-- Connect to database
-- Run these to create test data

-- Create test users
INSERT INTO users (user_id, timezone, last_xp_reset)
VALUES (123456789, 'America/New_York', CURRENT_DATE);

-- Create test characters
INSERT INTO characters (user_id, name, xp, daily_xp, daily_hf, char_buffer)
VALUES
  (123456789, 'Test Char 1', 1000, 5, 3, 100),
  (123456789, 'Test Char 2', 5000, 10, 5, 0),
  (123456789, 'Test Char 3', 15000, 0, 0, 50);

-- Set active character
UPDATE users SET active_character_id = (
  SELECT id FROM characters WHERE name = 'Test Char 1' LIMIT 1
) WHERE user_id = 123456789;
```

---

## Next Steps

- ✅ Bot running locally
- ✅ Database connected
- ✅ Commands working

**What's next?**
1. Test all bot commands thoroughly
2. Make your code changes
3. Add custom features
4. Prepare for production deployment (see `POSTGRES_SETUP.md`)

---

## Need Help?

- **Database issues:** See `POSTGRES_SETUP.md` → Troubleshooting section
- **Migration help:** See `MIGRATION_SUMMARY.md`
- **Discord.py docs:** https://discordpy.readthedocs.io/
- **asyncpg docs:** https://magicstack.github.io/asyncpg/

Happy coding! 🚀
