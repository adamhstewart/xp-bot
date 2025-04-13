import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones
import difflib
import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = int(os.getenv("GUILD_ID", 0))

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
XP_FILE = "xp.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# XP/Level config
LEVEL_THRESHOLDS = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000
]

DEFAULT_CONFIG = {
    "xp_channels": [],
    "char_per_xp": 240,
    "daily_xp_cap": 5
}

def load_xp():
    try:
        with open(XP_FILE, "r") as f:
            data = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = value
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()

def save_xp(data):
    with open(XP_FILE, "w") as f:
        json.dump(data, f, indent=4)

xp_data = load_xp()

def ensure_user(user_id):
    if user_id not in xp_data:
        xp_data[user_id] = {
            "active": None,
            "characters": {},
            "char_buffer": 0,
            "daily_xp": 0,
            "last_xp_reset": "",
            "timezone": "UTC"
        }

def has_role(user, allowed_roles):
    """Return True if user has at least one allowed role name."""
    return any(role.name in allowed_roles for role in getattr(user, 'roles', []))

def get_level_and_progress(xp):
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp < threshold:
            level = i
            break
    else:
        level = 20

    if level == 20:
        return level, None, None

    current_threshold = LEVEL_THRESHOLDS[level - 1]
    next_threshold = LEVEL_THRESHOLDS[level]
    progress = xp - current_threshold
    required = next_threshold - current_threshold
    return level, progress, required

def should_reset_xp(user_data):
    now_utc = datetime.utcnow()
    tz = user_data.get("timezone", "UTC")
    try:
        user_time = now_utc.astimezone(ZoneInfo(tz))
    except Exception:
        user_time = now_utc
    today_local = user_time.date().isoformat()
    return user_data.get("last_xp_reset") != today_local

@bot.event
async def on_ready():
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced slash commands to guild {GUILD_ID}")
    else:
        await bot.tree.sync()
        print("🌍 Synced slash commands globally")

    print(f"{bot.user.name} is online.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    channel_id = message.channel.id
    if channel_id not in xp_data.get("xp_channels", []):
        return

    user_id = str(message.author.id)
    ensure_user(user_id)

    user_data = xp_data[user_id]
    if should_reset_xp(user_data):
        user_data["daily_xp"] = 0
        try:
            tz = ZoneInfo(user_data.get("timezone", "UTC"))
            user_data["last_xp_reset"] = datetime.utcnow().astimezone(tz).date().isoformat()
        except:
            user_data["last_xp_reset"] = datetime.utcnow().date().isoformat()

    active = user_data["active"]
    if not active or active not in user_data["characters"]:
        return

    buffer = user_data.get("char_buffer", 0)
    buffer += len(message.content)

    char_per_xp = xp_data.get("char_per_xp", 240)
    potential_xp = buffer // char_per_xp
    xp_remaining = xp_data.get("daily_xp_cap", 5) - user_data["daily_xp"]
    gained_xp = min(potential_xp, xp_remaining)

    user_data["char_buffer"] = buffer % char_per_xp

    if gained_xp > 0:
        user_data["daily_xp"] += gained_xp
        user_data["characters"][active]["xp"] += gained_xp
        save_xp(xp_data)

# SLASH COMMANDS
@bot.tree.command(name="xp", description="View XP, level, and progress for a character")
@app_commands.describe(char_name="Optional character name (defaults to active)")
async def xp(interaction: discord.Interaction, char_name: str = None):
    user_id = str(interaction.user.id)
    ensure_user(user_id)

    characters = xp_data[user_id]["characters"]
    if not characters:
        await interaction.response.send_message("❌ You don’t have any characters yet.", ephemeral=True)
        return

    if not char_name:
        char_name = xp_data[user_id]["active"]
        if not char_name:
            await interaction.response.send_message("❌ No active character. Use `/xp_active` to set one.", ephemeral=True)
            return

    if char_name not in characters:
        matches = difflib.get_close_matches(char_name, characters.keys(), n=1, cutoff=0.6)
        if not matches:
            await interaction.response.send_message(f"❌ Character '{char_name}' not found.", ephemeral=True)
            return
        char_name = matches[0]

    char = characters[char_name]
    xp = char["xp"]
    level, progress, required = get_level_and_progress(xp)

    desc = f"XP: {xp}\nLevel: {level}"
    if progress is not None:
        bar = int((progress / required) * 20)
        desc += f"\nProgress: `[{'█'*bar}{'-'*(20-bar)}] {progress}/{required}`"

    embed = discord.Embed(title=char_name, description=desc)
    if char.get("image_url"):
        embed.set_image(url=char["image_url"])

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="xp_create", description="Create a new character")
@app_commands.describe(char_name="Character name", image_url="Optional image URL")
async def xp_create(interaction: discord.Interaction, char_name: str, image_url: str = None):
    user_id = str(interaction.user.id)
    ensure_user(user_id)

    if char_name in xp_data[user_id]["characters"]:
        await interaction.response.send_message(f"❌ Character '{char_name}' already exists.", ephemeral=True)
        return

    xp_data[user_id]["characters"][char_name] = {"xp": 0, "image_url": image_url or ""}
    if not xp_data[user_id]["active"]:
        xp_data[user_id]["active"] = char_name

    save_xp(xp_data)
    await interaction.response.send_message(
        f"✅ Character '{char_name}' created and set as active.",
        ephemeral=True
    )

    save_xp(xp_data)
    await interaction.response.send_message(f"✅ Character '{char_name}' created and set as active.", ephemeral=True)

@bot.tree.command(name="xp_delete")
@app_commands.describe(name="Character name to delete")
async def xp_delete(interaction: discord.Interaction, name: str):
    user_id = str(interaction.user.id)
    ensure_user(user_id)

    if name not in xp_data[user_id]["characters"]:
        await interaction.response.send_message("❌ Character not found.", ephemeral=True)
        return

    del xp_data[user_id]["characters"][name]
    if xp_data[user_id]["active"] == name:
        xp_data[user_id]["active"] = next(iter(xp_data[user_id]["characters"]), None)

    save_xp(xp_data)
    await interaction.response.send_message(f"🗑️ Deleted character '{name}'.", ephemeral=True)

@bot.tree.command(name="xp_active", description="Set which of your characters is currently active")
@app_commands.describe(char_name="Name of the character to activate")
async def xp_active(interaction: discord.Interaction, char_name: str):
    user_id = str(interaction.user.id)
    ensure_user(user_id)

    chars = xp_data[user_id]["characters"]
    if not chars:
        await interaction.response.send_message("❌ You have no characters to activate.", ephemeral=True)
        return

    # Fuzzy match if exact name isn't found
    if char_name not in chars:
        matches = difflib.get_close_matches(char_name, chars.keys(), n=1, cutoff=0.6)
        if not matches:
            await interaction.response.send_message(f"❌ No character found matching '{char_name}'.", ephemeral=True)
            return
        char_name = matches[0]

    xp_data[user_id]["active"] = char_name
    save_xp(xp_data)
    await interaction.response.send_message(f"🟢 '{char_name}' is now your active character.", ephemeral=True)

@bot.tree.command(name="xp_list")
async def xp_list(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    ensure_user(user_id)
    chars = xp_data[user_id]["characters"]
    active = xp_data[user_id]["active"]

    if not chars:
        await interaction.response.send_message("You have no characters.", ephemeral=True)
        return

    lines = []
    for name, data in chars.items():
        mark = "🟢" if name == active else "⚪"
        lines.append(f"{mark} {name} — {data['xp']} XP")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@bot.tree.command(name="xp_enable")
@app_commands.describe(channel="Channel to enable XP tracking")
async def xp_enable(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    if channel.id not in xp_data["xp_channels"]:
        xp_data["xp_channels"].append(channel.id)
        save_xp(xp_data)

    await interaction.response.send_message(f"✅ XP tracking enabled in {channel.mention}.", ephemeral=True)

@bot.tree.command(name="xp_disable")
@app_commands.describe(channel="Channel to disable XP tracking")
async def xp_disable(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    if channel.id in xp_data["xp_channels"]:
        xp_data["xp_channels"].remove(channel.id)
        save_xp(xp_data)

    await interaction.response.send_message(f"🚫 XP tracking disabled in {channel.mention}.", ephemeral=True)

@bot.tree.command(name="xp_tracking")
async def xp_tracking(interaction: discord.Interaction):
    channel_ids = xp_data.get("xp_channels", [])
    if not channel_ids:
        await interaction.response.send_message("No channels have XP tracking enabled.", ephemeral=True)
        return

    mentions = [f"<#{cid}>" for cid in channel_ids]
    await interaction.response.send_message("📍 XP is tracked in:\n" + "\n".join(mentions), ephemeral=True)

@bot.tree.command(name="xp_set_cap")
@app_commands.describe(amount="New daily XP cap")
async def xp_set_cap(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    if amount < 1:
        await interaction.response.send_message("❌ Cap must be at least 1.", ephemeral=True)
        return

    xp_data["daily_xp_cap"] = amount
    save_xp(xp_data)
    await interaction.response.send_message(f"✅ Daily XP cap set to {amount}.", ephemeral=True)

@bot.tree.command(name="xp_set_timezone")
@app_commands.describe(timezone="Your timezone, e.g. America/New_York")
async def xp_set_timezone(interaction: discord.Interaction, timezone: str):
    user_id = str(interaction.user.id)
    ensure_user(user_id)

    try:
        ZoneInfo(timezone)
    except:
        await interaction.response.send_message("❌ Invalid timezone.", ephemeral=True)
        return

    xp_data[user_id]["timezone"] = timezone
    save_xp(xp_data)
    await interaction.response.send_message(f"✅ Timezone set to {timezone}.", ephemeral=True)

@bot.tree.command(name="xp_help")
async def xp_help(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 XP Bot Help", description="Slash commands to manage your XP and characters:")
    embed.add_field(name="/xp_create", value="Create a new character.", inline=False)
    embed.add_field(name="/xp_active", value="Set which character is active.", inline=False)
    embed.add_field(name="/xp_me", value="View your active or named character.", inline=False)
    embed.add_field(name="/xp", value="Check XP for a character.", inline=False)
    embed.add_field(name="/xp_list", value="List all your characters.", inline=False)
    embed.add_field(name="/xp_delete", value="Delete a character.", inline=False)
    embed.add_field(name="/xp_enable / /xp_disable", value="Enable or disable XP tracking in a channel.", inline=False)
    embed.add_field(name="/xp_tracking", value="List channels where XP tracking is enabled.", inline=False)
    embed.add_field(name="/xp_set_cap", value="(Admin) Set the daily XP cap.", inline=False)
    embed.add_field(name="/xp_set_timezone", value="Set your personal XP reset timezone.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
