# XP Bot

A Discord bot for role-playing communities to track experience points (XP) from RP messages and other activities.

Built with Python, Discord.py, and PostgreSQL.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Database](#database)
- [Code Structure](#code-structure)
- [Troubleshooting](#troubleshooting)
- [Migration Guide](#migration-guide)

---

## Features

### Character Management
- Create and manage multiple characters per user
- Set active character for automatic RP XP tracking
- View character XP, level (1-20), and progress bars
- Character images and sheet URLs in XP displays
- Retire characters (soft delete) with preservation of data
- Admin tools for character restoration and data purging (GDPR)

### RP (Role-Play) Tracking
- Automatic XP from messages in designated RP channels
- Configurable character-per-XP ratio (default: 240 chars = 1 XP)
- Daily XP caps to prevent grinding
- Character buffer system for partial XP accumulation

### HF (Hunting/Foraging) Tracking
- Automatic XP from bot-generated hunting/foraging activities
- Configurable XP for attempts and successes
- Separate daily caps for HF activities
- Smart character name disambiguation for duplicate names

### Admin Features
- Channel-based XP tracking configuration
- Customizable XP rates and daily caps
- Manual XP grant/removal for any character
- Interactive settings UI with modals and dropdowns

### User Features
- Personal timezone settings for accurate daily resets
- Fuzzy character name matching
- Rate limiting to prevent abuse
- Input validation for all commands

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (recommended)
- **Discord Bot Token** ([Get one here](https://discord.com/developers/applications))
- **Discord Server** with Guild ID

### 1. Clone & Setup

```bash
cd xp-bot

# Create .env file
cat > .env << EOF
DISCORD_BOT_TOKEN=your_token_here
GUILD_ID=your_guild_id_here
ENV=dev
EOF
```

### 2. Run with Docker Compose

```bash
# Start PostgreSQL and bot
docker-compose up

# Or run in background
docker-compose up -d
```

That's it! The bot should now be online.

### 3. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create application → Go to "Bot" section
3. **Enable Intents:**
   - Server Members Intent
   - Message Content Intent
4. Copy bot token → Add to `.env` as `DISCORD_BOT_TOKEN`
5. **Invite bot** with this URL:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=274878285888&scope=bot%20applications.commands
   ```
   Replace `YOUR_CLIENT_ID` with your Application ID
6. Get Guild ID: Enable Developer Mode → Right-click server → Copy Server ID

---

## Commands

### Character Management

| Command | Description | Example |
|---------|-------------|---------|
| `/xp_create` | Create a new character | `/xp_create char_name:Luna sheet_url:https://... image_url:https://...` |
| `/xp` | View characters with navigation, set active, retire, or view other users | `/xp` or `/xp user:@Player` |
| `/xp_edit` | Edit character details (name, image, sheet) | `/xp_edit char_name:Luna new_name:Luna-2` |
| `/xp_request` | Request XP for a character (admin approval) | `/xp_request char_name:Luna amount:100 memo:"Completed quest"` |
| `/xp_retire` | **(Admin)** Retire a character (soft delete, can be restored) | `/xp_retire character_name:Luna` |

### Info Commands

| Command | Description |
|---------|-------------|
| `/xp_help` | Show command help |
| `/xp_tracking` | List XP-tracked channels |
| `/xp_set_timezone` | Set your timezone for daily resets |
| `/xp_sync` | Re-sync slash commands |

### Admin Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/xp_grant` | Grant/remove XP | `/xp_grant character_name:Luna amount:100 memo:"Quest reward"` |
| `/xp_retire` | Retire a character (soft delete, restorable) | `/xp_retire character_name:Luna` |
| `/xp_purge` | **Permanently** delete user and all their data (GDPR) | `/xp_purge user:@Player` |
| `/xp_add_rp_channel` | Enable RP tracking in channel | `/xp_add_rp_channel channel:#rp` |
| `/xp_remove_rp_channel` | Disable RP tracking | `/xp_remove_rp_channel channel:#rp` |
| `/xp_add_hf_channel` | Enable HF tracking | `/xp_add_hf_channel channel:#hunting` |
| `/xp_remove_hf_channel` | Disable HF tracking | `/xp_remove_hf_channel channel:#hunting` |
| `/xp_set_cap` | Set daily RP XP cap | `/xp_set_cap amount:10` |
| `/xp_config_hf` | Configure HF XP rates | `/xp_config_hf attempt_xp:1 success_xp:5 daily_cap:10` |
| `/xp_add_admin_role` | Add role with XP admin permissions | `/xp_add_admin_role role:@GameMaster` |
| `/xp_remove_admin_role` | Remove XP admin permissions | `/xp_remove_admin_role role:@GameMaster` |
| `/xp_list_admin_roles` | List roles with XP admin permissions | `/xp_list_admin_roles` |
| `/xp_set_log_channel` | Set channel for XP activity logging | `/xp_set_log_channel channel:#xp-log` |

### Legacy Commands

| Command | Description |
|---------|-------------|
| `!xpsettings` | Interactive settings UI (buttons & modals) |
| `!sync` | Sync commands to current guild |

---

## Local Development

### Option 1: Docker Compose (Recommended)

```bash
# Start services
docker-compose up

# View logs
docker-compose logs -f xp-bot

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose build xp-bot && docker-compose restart xp-bot
```

**Auto-restart:** The Docker setup uses `watchmedo` to automatically restart when Python files change.

### Option 2: Manual Setup

#### 1. Install PostgreSQL

**macOS:**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Linux:**
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

#### 2. Create Database

```bash
psql postgres
CREATE DATABASE xpbot;
CREATE USER xpbot WITH PASSWORD 'dev_password';
GRANT ALL PRIVILEGES ON DATABASE xpbot TO xpbot;
\q
```

#### 3. Install Python Dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 4. Configure Environment

```bash
cat > .env << EOF
DISCORD_BOT_TOKEN=your_token_here
GUILD_ID=your_guild_id_here
DATABASE_URL=postgresql://xpbot:dev_password@localhost:5432/xpbot
ENV=dev
EOF
```

#### 5. Run Bot

```bash
python bot.py
```

### Database Access

**With Docker:**
```bash
docker-compose exec postgres psql -U xpbot -d xpbot
```

**Without Docker:**
```bash
psql -U xpbot -d xpbot
```

**Useful SQL queries:**
```sql
-- View all characters with XP
SELECT u.user_id, c.name, c.xp, c.daily_xp
FROM characters c
JOIN users u ON c.user_id = u.user_id
ORDER BY c.xp DESC;

-- View guild configuration
SELECT * FROM config;

-- Find top 10 characters
SELECT name, xp FROM characters ORDER BY xp DESC LIMIT 10;
```

### Recommended Tools

- **pgAdmin** - Full-featured PostgreSQL GUI
- **DBeaver** - Cross-platform database tool
- **TablePlus** - macOS/Windows (paid)

**Connection details:**
- Host: `localhost`
- Port: `5432`
- Database: `xpbot`
- User: `xpbot`
- Password: `xpbot_dev_password` (Docker) or your custom password

---

## Production Deployment

This guide will walk you through deploying XP Bot to Fly.io with a PostgreSQL database.

### Prerequisites

1. **Fly.io Account**: Sign up at https://fly.io/
2. **Fly CLI**: Install the Fly CLI tool
3. **Discord Bot Token**: From Discord Developer Portal
4. **Guild ID**: Your Discord server ID

### Step 1: Install Fly CLI

**macOS/Linux:**
```bash
curl -L https://fly.io/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

Verify installation:
```bash
fly version
```

### Step 2: Login to Fly.io

```bash
fly auth login
```

This will open a browser window for authentication.

### Step 3: Update fly.toml (if needed)

Edit `fly.toml` and update the app name if needed:
```toml
app = 'xp-bot'  # Change to your desired app name (must be globally unique)
primary_region = 'iad'  # Change to your preferred region
```

**Available regions** (check with `fly platform regions`):
- `iad` - Ashburn, Virginia (US East)
- `lax` - Los Angeles, California (US West)
- `lhr` - London, UK
- `fra` - Frankfurt, Germany
- `syd` - Sydney, Australia
- `nrt` - Tokyo, Japan

### Step 4: Create PostgreSQL Database

Create a Postgres cluster (choose a name like `xp-bot-db`):

```bash
fly postgres create --name xp-bot-db --region iad --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1
```

**Options explained:**
- `--name`: Name of your database cluster
- `--region`: Must match your app's region
- `--initial-cluster-size 1`: Single instance (cheaper, sufficient for most bots)
- `--vm-size shared-cpu-1x`: Smallest VM (256MB RAM, ~$1.94/month)
- `--volume-size 1`: 1GB storage (plenty for a Discord bot)

**For larger deployments:**
```bash
# High-availability setup (2 instances, auto-failover)
fly postgres create --name xp-bot-db --region iad --initial-cluster-size 2 --vm-size shared-cpu-2x --volume-size 3
```

### Step 5: Launch the App (Initial Setup)

```bash
fly launch --no-deploy
```

This will:
- Detect your Dockerfile
- Read your `fly.toml`
- Create the app on Fly.io
- **NOT** deploy yet (we need to set secrets first)

If it asks to tweak settings, say **No** (we already configured fly.toml).

### Step 6: Attach Database to App

```bash
fly postgres attach xp-bot-db --app xp-bot
```

This automatically sets the `DATABASE_URL` secret for your app.

Verify the connection string was set:
```bash
fly secrets list
```

You should see `DATABASE_URL` in the list.

### Step 7: Set Environment Secrets

Set your Discord bot token and guild ID:

```bash
fly secrets set DISCORD_BOT_TOKEN="your_bot_token_here"
fly secrets set GUILD_ID="your_guild_id_here"
```

**Important:** Replace with your actual values!

Verify all secrets are set:
```bash
fly secrets list
```

You should see:
- `DATABASE_URL`
- `DISCORD_BOT_TOKEN`
- `GUILD_ID`

### Step 8: Deploy!

```bash
fly deploy
```

This will:
1. Build the Docker image from `Dockerfile.prod`
2. Push to Fly.io registry
3. Create a VM and start your bot
4. Run database schema initialization automatically

**Watch the deployment:**
```bash
fly status
```

### Step 9: Monitor Logs

Watch your bot start up:

```bash
fly logs
```

Look for these success messages:
```
✅ Database connected successfully
✅ Database schema initialized
✅ Bot 'XP-Bot' is online
✅ Synced 29 slash commands
```

**To follow logs in real-time:**
```bash
fly logs -f
```

### Step 10: Verify Bot is Online

1. Check Discord - your bot should show as online
2. Try `/xp_help` in your Discord server
3. Create a test character with `/xp_create`

### Managing Your Deployment

#### View App Status
```bash
fly status
```

#### Restart the Bot
```bash
fly apps restart xp-bot
```

#### Scale Resources (if needed)

**Increase memory** (if bot runs out):
```bash
fly scale memory 512
```

**Check current scaling:**
```bash
fly scale show
```

#### Update the Bot (Deploy Changes)

After making code changes:

```bash
fly deploy
```

#### Access PostgreSQL Directly

**Via proxy** (recommended for management):
```bash
# Start proxy on localhost:5432
fly proxy 5432 -a xp-bot-db

# In another terminal, connect with psql
psql postgresql://xpbot:password@localhost:5432/xpbot
```

**Via SSH:**
```bash
fly ssh console -a xp-bot-db
# Then run: su - postgres && psql
```

#### View Database Connection String
```bash
fly secrets list
```

#### Backup Database

**Create snapshot:**
```bash
fly volumes snapshots create vol_xxx -a xp-bot-db
```

**List snapshots:**
```bash
fly volumes snapshots list -a xp-bot-db
```

### Troubleshooting Deployment

#### Bot Not Starting

**Check logs:**
```bash
fly logs
```

**Common issues:**
- `DATABASE_URL environment variable not set` → Re-run `fly postgres attach`
- `discord.errors.LoginFailure` → Check `DISCORD_BOT_TOKEN` secret
- `asyncpg.InvalidPasswordError` → Database attachment failed, try detaching and re-attaching

#### Database Connection Issues

**Test connection:**
```bash
fly ssh console
# Inside VM:
python -c "import os; print(os.getenv('DATABASE_URL'))"
```

**Reconnect database:**
```bash
fly postgres detach xp-bot-db
fly postgres attach xp-bot-db
```

#### Out of Memory

**Check usage:**
```bash
fly status
```

**Scale up:**
```bash
fly scale memory 512  # Increase to 512MB
```

#### Commands Not Syncing

**Restart bot:**
```bash
fly apps restart xp-bot
```

**Check guild ID:**
```bash
fly ssh console
python -c "import os; print(os.getenv('GUILD_ID'))"
```

### Costs (Approximate)

**Minimal setup:**
- Bot VM (256MB): **$1.94/month**
- PostgreSQL (shared-cpu-1x, 1GB): **$1.94/month**
- **Total: ~$3.88/month**

**Recommended for production:**
- Bot VM (512MB): **$3.88/month**
- PostgreSQL HA (2x shared-cpu-1x, 3GB): **~$8/month**
- **Total: ~$12/month**

**Free tier allowances** (check current limits):
- $5/month free credits (covers minimal setup partially)
- First 3 shared-cpu-1x VMs included

Check your bill:
```bash
fly billing show
```

### Updating Configuration

#### Change VM Size
```bash
fly scale vm shared-cpu-2x  # Upgrade to 512MB
```

#### Change Region
You'll need to create a new app in the desired region:
```bash
fly apps create xp-bot-new --region lhr
fly postgres create --name xp-bot-db-new --region lhr
# Then deploy to new app
```

#### Environment Variables

**Set new secret:**
```bash
fly secrets set NEW_VAR="value"
```

**Update existing:**
```bash
fly secrets set DISCORD_BOT_TOKEN="new_token"
```

**Remove secret:**
```bash
fly secrets unset VARIABLE_NAME
```

### Monitoring & Maintenance

#### View Metrics
```bash
fly dashboard  # Opens web dashboard
```

#### Check App Health
```bash
fly status
fly logs --tail 100
```

#### Update Bot Code
```bash
git pull  # Get latest code
fly deploy  # Deploy update
```

### Migrating Existing Data

If you have an existing database dump:

```bash
# Create proxy
fly proxy 5432 -a xp-bot-db

# In another terminal, restore
pg_restore -h localhost -U xpbot -d xpbot backup.dump
```

### Destroying Resources

**CAUTION: This permanently deletes everything!**

```bash
# Delete app
fly apps destroy xp-bot

# Delete database (DESTROYS ALL DATA)
fly apps destroy xp-bot-db
```

### Deployment Support

- Fly.io Docs: https://fly.io/docs/
- Fly.io Community: https://community.fly.io/
- Discord.py Docs: https://discordpy.readthedocs.io/

### Security Notes

1. **Never commit secrets** to git (.env is gitignored)
2. **Rotate tokens** if exposed
3. **Use Fly secrets** for all sensitive data
4. **Enable 2FA** on Fly.io account
5. **Regularly update dependencies** (`pip install --upgrade`)

### Next Steps

After deployment:
1. Monitor logs for a few hours
2. Test all commands in Discord
3. Set up uptime monitoring (optional)
4. Configure automated backups (optional)
5. Document any custom configurations

---

## Database

### Schema

**config** - Guild-wide settings
- `rp_channels[]` - RP tracking channels
- `hf_channels[]` - HF tracking channels
- `char_per_rp` - Characters needed per XP
- `daily_rp_cap` - Daily RP XP limit
- `hf_attempt_xp`, `hf_success_xp`, `daily_hf_cap` - HF settings

**users** - Discord users
- `user_id` (PK) - Discord user ID
- `active_character_id` (FK) - Currently active character
- `timezone` - User's timezone for daily resets
- `last_xp_reset` - Last daily reset date

**characters** - User characters
- `id` (PK) - Auto-increment ID
- `user_id` (FK) - Owner's Discord ID
- `name` - Character name (unique per user)
- `xp` - Total XP
- `daily_xp`, `daily_hf` - Daily counters
- `char_buffer` - Partial XP accumulator
- `image_url` - Character image

#---

## Code Structure

```
xp-bot/
├── bot.py                    # Main entry point (62 lines)
├── database.py               # Database layer with asyncpg
├── schema.sql                # PostgreSQL schema
├── commands/                 # Slash commands by category
│   ├── character.py          # Character management (161 lines)
│   ├── admin.py              # Admin configuration (177 lines)
│   └── info.py               # Help and info (69 lines)
├── handlers/                 # Event and error handlers
│   ├── events.py             # on_ready, on_message (160 lines)
│   └── errors.py             # Error handling (62 lines)
├── ui/                       # Discord UI components
│   ├── modals.py             # Configuration modals (88 lines)
│   └── views.py              # Buttons and dropdowns (74 lines)
└── utils/                    # Utility functions
    ├── validation.py         # Input validation (121 lines)
    ├── xp.py                 # XP calculations (59 lines)
    └── permissions.py        # Permission checks (8 lines)
```

---

## Troubleshooting

### Bot Not Starting

**"DATABASE_URL environment variable not set"**
```bash
# Add to .env file
DATABASE_URL=postgresql://xpbot:xpbot_dev_password@localhost:5432/xpbot
```

**"Connection refused"**
```bash
# Check if PostgreSQL is running
docker-compose ps                          # Docker
brew services list                         # macOS
sudo systemctl status postgresql           # Linux
```

**"asyncpg module not found"**
```bash
pip install -r requirements.txt
# Or rebuild Docker:
docker-compose build --no-cache
```

### Bot Not Responding to Commands

1. **Check bot is online:**
   - Look for `✅ xp-bot is online` in logs
   - Bot shows online in Discord

2. **Check commands synced:**
   - Look for `✅ Synced X slash commands` in logs
   - Type `/xp` in Discord - should show autocomplete

3. **Sync manually:**
   ```
   /xp_sync
   ```

4. **Check permissions:**
   - Bot needs `applications.commands` scope
   - Reinvite with correct permissions

### Commands Not Working

**"relation does not exist" / "table not found"**

Schema wasn't created. Restart bot - it auto-creates tables:
```bash
docker-compose restart xp-bot
# Or:
python bot.py
```

**Rate limit errors**

Wait for cooldown period to expire. Rate limits:
- Character commands: 3-5 uses per 10-60s
- Admin commands: 3-10 uses per 60s
- Info commands: 1-3 uses per 60s

### Docker Issues

**Changes not taking effect:**
```bash
docker-compose build
docker-compose up --force-recreate
```

**Bot crash loop:**
```bash
# View error logs
docker-compose logs xp-bot

# Common causes:
# - Invalid DISCORD_BOT_TOKEN
# - DATABASE_URL not set
# - Syntax error in code
```

### Database Issues

**Reset database (CAREFUL - deletes all data):**
```bash
# Docker
docker-compose down -v
docker-compose up

# Manual
dropdb xpbot
createdb xpbot
python bot.py
```

**View database size:**
```sql
SELECT pg_size_pretty(pg_database_size('xpbot'));
```

---

## Migration Guide

### Migrating from JSON Storage

If upgrading from an older version that used `xp.json`:

1. **Backup your data:**
   ```bash
   cp xp.json xp.json.backup
   ```

2. **Run migration script:**
   ```bash
   # Ensure DATABASE_URL is set
   export DATABASE_URL="postgresql://xpbot:password@localhost:5432/xpbot"
   python migrate_to_postgres.py
   ```

3. **Verify migration:**
   ```sql
   -- Check users
   SELECT COUNT(*) FROM users;

   -- Check characters
   SELECT COUNT(*) FROM characters;

   -- Check config
   SELECT * FROM config;
   ```

4. **Test bot:**
   - Create test character: `/xp_create char_name:Test`
   - View character: `/xp`
   - Send RP message to verify XP tracking


---

## Contributing

### Development Workflow

1. Make code changes
2. Bot auto-restarts (Docker) or manually restart
3. Test commands in Discord
4. Check logs for errors
5. Commit when ready

### Code Style

- Use async/await for database operations
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Validate all user input
- Keep functions small and focused
- Add docstrings to new functions

### Adding New Commands

1. Choose appropriate module: `commands/character.py`, `commands/admin.py`, or `commands/info.py`
2. Add command with decorator:
   ```python
   @bot.tree.command(name="xp_mycommand")
   @app_commands.checks.cooldown(3, 60.0, key=lambda i: i.user.id)
   async def my_command(interaction: discord.Interaction):
       # Implementation
   ```
3. Register in `bot.py` if adding new module
4. Test and commit

---

## License

XP-Bot: Discord XP Tracking Bot
Copyright (c) 2025 Adam Stewart
Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
You may obtain a copy of the License at https://www.gnu.org/licenses/agpl-3.0.en.html


## Support

- Report issues: [GitHub Issues](https://github.com/your-repo/issues)
- Documentation: This README

---

**Version:** 2.0.0 (PostgreSQL + Modular Architecture)
**Python:** 3.11+
**Database:** PostgreSQL 15+
