# XP Bot - Production Deployment Guide (Fly.io)

This guide will walk you through deploying XP Bot to Fly.io with a PostgreSQL database.

## Prerequisites

1. **Fly.io Account**: Sign up at https://fly.io/
2. **Fly CLI**: Install the Fly CLI tool
3. **Discord Bot Token**: From Discord Developer Portal
4. **Guild ID**: Your Discord server ID

## Step 1: Install Fly CLI

### macOS/Linux
```bash
curl -L https://fly.io/install.sh | sh
```

### Windows (PowerShell)
```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

Verify installation:
```bash
fly version
```

## Step 2: Login to Fly.io

```bash
fly auth login
```

This will open a browser window for authentication.

## Step 3: Update fly.toml (if needed)

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

## Step 4: Create PostgreSQL Database

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

## Step 5: Launch the App (Initial Setup)

```bash
fly launch --no-deploy
```

This will:
- Detect your Dockerfile
- Read your `fly.toml`
- Create the app on Fly.io
- **NOT** deploy yet (we need to set secrets first)

If it asks to tweak settings, say **No** (we already configured fly.toml).

## Step 6: Attach Database to App

```bash
fly postgres attach xp-bot-db --app xp-bot
```

This automatically sets the `DATABASE_URL` secret for your app.

Verify the connection string was set:
```bash
fly secrets list
```

You should see `DATABASE_URL` in the list.

## Step 7: Set Environment Secrets

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

## Step 8: Deploy!

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

## Step 9: Monitor Logs

Watch your bot start up:

```bash
fly logs
```

Look for these success messages:
```
✅ Database connected successfully
✅ Database schema initialized
✅ Bot 'XP-Bot' is online
✅ Synced 21 slash commands
```

**To follow logs in real-time:**
```bash
fly logs -f
```

## Step 10: Verify Bot is Online

1. Check Discord - your bot should show as online
2. Try `/xp_help` in your Discord server
3. Create a test character with `/xp_create`

## Managing Your Deployment

### View App Status
```bash
fly status
```

### Restart the Bot
```bash
fly apps restart xp-bot
```

### Scale Resources (if needed)

**Increase memory** (if bot runs out):
```bash
fly scale memory 512
```

**Check current scaling:**
```bash
fly scale show
```

### Update the Bot (Deploy Changes)

After making code changes:

```bash
fly deploy
```

### Access PostgreSQL Directly

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

### View Database Connection String
```bash
fly secrets list
```

### Backup Database

**Create snapshot:**
```bash
fly volumes snapshots create vol_xxx -a xp-bot-db
```

**List snapshots:**
```bash
fly volumes snapshots list -a xp-bot-db
```

## Troubleshooting

### Bot Not Starting

**Check logs:**
```bash
fly logs
```

**Common issues:**
- `DATABASE_URL environment variable not set` → Re-run `fly postgres attach`
- `discord.errors.LoginFailure` → Check `DISCORD_BOT_TOKEN` secret
- `asyncpg.InvalidPasswordError` → Database attachment failed, try detaching and re-attaching

### Database Connection Issues

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

### Out of Memory

**Check usage:**
```bash
fly status
```

**Scale up:**
```bash
fly scale memory 512  # Increase to 512MB
```

### Commands Not Syncing

**Restart bot:**
```bash
fly apps restart xp-bot
```

**Check guild ID:**
```bash
fly ssh console
python -c "import os; print(os.getenv('GUILD_ID'))"
```

## Costs (Approximate)

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

## Updating Configuration

### Change VM Size
```bash
fly scale vm shared-cpu-2x  # Upgrade to 512MB
```

### Change Region
You'll need to create a new app in the desired region:
```bash
fly apps create xp-bot-new --region lhr
fly postgres create --name xp-bot-db-new --region lhr
# Then deploy to new app
```

### Environment Variables

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

## Monitoring & Maintenance

### View Metrics
```bash
fly dashboard  # Opens web dashboard
```

### Check App Health
```bash
fly status
fly logs --tail 100
```

### Update Bot Code
```bash
git pull  # Get latest code
fly deploy  # Deploy update
```

## Migrating Existing Data

If you have an existing database dump:

```bash
# Create proxy
fly proxy 5432 -a xp-bot-db

# In another terminal, restore
pg_restore -h localhost -U xpbot -d xpbot backup.dump
```

## Destroying Resources

**CAUTION: This permanently deletes everything!**

```bash
# Delete app
fly apps destroy xp-bot

# Delete database (DESTROYS ALL DATA)
fly apps destroy xp-bot-db
```

## Support

- Fly.io Docs: https://fly.io/docs/
- Fly.io Community: https://community.fly.io/
- Discord.py Docs: https://discordpy.readthedocs.io/

## Security Notes

1. **Never commit secrets** to git (.env is gitignored)
2. **Rotate tokens** if exposed
3. **Use Fly secrets** for all sensitive data
4. **Enable 2FA** on Fly.io account
5. **Regularly update dependencies** (`pip install --upgrade`)

## Next Steps

After deployment:
1. Monitor logs for a few hours
2. Test all commands in Discord
3. Set up uptime monitoring (optional)
4. Configure automated backups (optional)
5. Document any custom configurations

---

**Deployment complete!** Your bot should now be running 24/7 on Fly.io. 🚀
