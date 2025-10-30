# PostgreSQL Setup Guide

This guide walks you through setting up PostgreSQL for the XP Bot.

## Local Development Setup

### Option 1: Docker Compose (Recommended)

1. **Create docker-compose.yml** (already included in the repo):

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: xpbot
      POSTGRES_PASSWORD: xpbot_dev_password
      POSTGRES_DB: xpbot
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  bot:
    build: .
    environment:
      DATABASE_URL: postgresql://xpbot:xpbot_dev_password@postgres:5432/xpbot
      DISCORD_BOT_TOKEN: ${DISCORD_BOT_TOKEN}
      GUILD_ID: ${GUILD_ID}
      ENV: dev
    depends_on:
      - postgres
    volumes:
      - .:/app
    command: watchmedo auto-restart -d . -p '*.py' -- python bot.py

volumes:
  postgres_data:
```

2. **Start the services**:

```bash
docker-compose up
```

3. **Run the migration** (in another terminal):

```bash
# Set DATABASE_URL for local Postgres
export DATABASE_URL="postgresql://xpbot:xpbot_dev_password@localhost:5432/xpbot"

# Run migration script
python migrate_to_postgres.py
```

### Option 2: Local PostgreSQL Installation

1. **Install PostgreSQL** (macOS example):

```bash
brew install postgresql@15
brew services start postgresql@15
```

2. **Create database and user**:

```bash
psql postgres
```

```sql
CREATE DATABASE xpbot;
CREATE USER xpbot WITH PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE xpbot TO xpbot;
\q
```

3. **Set environment variable**:

```bash
export DATABASE_URL="postgresql://xpbot:your_password_here@localhost:5432/xpbot"
```

4. **Run the migration**:

```bash
python migrate_to_postgres.py
```

5. **Run the bot**:

```bash
python bot.py
```

---

## Fly.io Production Setup

### Step 1: Create a Fly Postgres Cluster

```bash
# Create a Postgres cluster in Fly.io
fly postgres create --name xp-bot-db

# Follow the prompts:
# - Choose a region (same as your app for lower latency)
# - Choose configuration (Development or Production)
# - Select Fly Postgres version (15 recommended)
```

**Important**: Save the connection string shown after creation! It looks like:
```
postgres://postgres:password@xp-bot-db.internal:5432
```

### Step 2: Attach Database to Your App

```bash
# Attach the Postgres cluster to your xp-bot app
fly postgres attach xp-bot-db --app xp-bot
```

This automatically sets the `DATABASE_URL` secret in your app.

### Step 3: Verify Database Connection

```bash
# Check that DATABASE_URL is set
fly secrets list --app xp-bot

# You should see DATABASE_URL in the output
```

### Step 4: Run the Migration

You have two options to run the migration:

#### Option A: Run Locally Against Fly Database (Recommended)

1. **Create a proxy to your Fly Postgres**:

```bash
# In one terminal, create a proxy
fly proxy 5432 -a xp-bot-db
```

2. **In another terminal, get the connection details**:

```bash
# Get connection string
fly postgres connect -a xp-bot-db --command "SELECT current_database(), current_user;"

# Or view all connection info
fly postgres connect -a xp-bot-db --command "\conninfo"
```

3. **Set DATABASE_URL with the proxy** (update password):

```bash
export DATABASE_URL="postgresql://postgres:your_password@localhost:5432/xp_bot"
```

4. **Run the migration**:

```bash
python migrate_to_postgres.py
```

#### Option B: Run Migration via Fly SSH

1. **Copy xp.json to the Fly app**:

```bash
fly ssh sftp shell
> put xp.json
> exit
```

2. **SSH into the app and run migration**:

```bash
fly ssh console --app xp-bot

# Inside the container
python migrate_to_postgres.py
exit
```

### Step 5: Deploy Your App

```bash
# Deploy the updated app
fly deploy

# Monitor logs
fly logs --app xp-bot
```

### Step 6: Verify Everything Works

```bash
# Check app status
fly status --app xp-bot

# Watch logs for successful connection
fly logs --app xp-bot

# You should see:
# ✅ Database connected
# ✅ Database schema initialized
# ✅ xp-bot is online.
```

---

## Database Backup & Maintenance

### Create a Backup

```bash
# Fly.io automatically creates backups, but you can manually trigger one
fly postgres backup create --app xp-bot-db
```

### List Backups

```bash
fly postgres backup list --app xp-bot-db
```

### Connect to Database Console

```bash
# Connect to Postgres console
fly postgres connect -a xp-bot-db
```

Example queries:

```sql
-- Check users
SELECT user_id, timezone, last_xp_reset FROM users;

-- Check characters
SELECT u.user_id, c.name, c.xp, c.daily_xp, c.daily_hf
FROM characters c
JOIN users u ON c.user_id = u.user_id
ORDER BY c.xp DESC
LIMIT 10;

-- Check config
SELECT * FROM config;
```

---

## Troubleshooting

### "Database connection failed"

1. **Check DATABASE_URL is set**:

```bash
fly secrets list --app xp-bot
```

2. **Verify Postgres cluster is running**:

```bash
fly status --app xp-bot-db
```

3. **Check Postgres logs**:

```bash
fly logs --app xp-bot-db
```

### "asyncpg.exceptions.InvalidCatalogNameError: database does not exist"

The database was not created. Fly Postgres should create it automatically, but you can create it manually:

```bash
fly postgres connect -a xp-bot-db
CREATE DATABASE xp_bot;
```

### "Migration script fails"

1. **Ensure xp.json is valid JSON**:

```bash
python -m json.tool xp.json
```

2. **Check DATABASE_URL format**:

```
postgresql://user:password@host:port/database
```

3. **Verify database connection**:

```python
import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect('your_database_url')
    print(await conn.fetchval('SELECT 1'))
    await conn.close()

asyncio.run(test())
```

---

## Scaling Considerations

### Development Config
- 1 shared CPU
- 256MB RAM
- Single instance

### Production Config (Recommended for active servers)
- 1-2 dedicated CPUs
- 512MB - 1GB RAM
- 2 instances (for high availability)
- Enable autoscaling

```bash
# Scale Postgres cluster
fly scale vm shared-cpu-1x --memory 512 --app xp-bot-db

# Scale bot app
fly scale count 2 --app xp-bot
```

---

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `DISCORD_BOT_TOKEN` | Discord bot token | `your_token_here` |
| `GUILD_ID` | Discord server ID | `123456789` |
| `ENV` | Environment mode | `dev` or `prod` |

---

## Security Best Practices

1. **Never commit DATABASE_URL** - Keep it in secrets/environment variables
2. **Use strong passwords** - Generated passwords for production
3. **Regular backups** - Enable automatic backups on Fly.io
4. **Monitor access** - Review Postgres logs periodically
5. **Update regularly** - Keep PostgreSQL and dependencies updated

---

## Cost Estimation (Fly.io)

**Development Setup**:
- Postgres (shared-cpu-1x, 256MB): ~$0-2/month
- Bot app (shared-cpu-1x): ~$0-2/month
- **Total**: ~$0-4/month (often free tier)

**Production Setup**:
- Postgres (dedicated-cpu-1x, 512MB, HA): ~$15-20/month
- Bot app (shared-cpu-1x, 2 instances): ~$4-8/month
- **Total**: ~$20-30/month

Check current pricing: https://fly.io/docs/about/pricing/
