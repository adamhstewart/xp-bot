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
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# XP/Level config
LEVEL_THRESHOLDS = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000
]

DEFAULT_CONFIG = {
    "rp_channels": [],
    "char_per_rp": 240,
    "daily_rp_cap": 5,
    "hf_channels": [],
    "hf_attempt_xp": 1,
    "hf_success_xp": 5,
    "daily_hf_cap": 5
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
            "daily_hf": 0,
            "last_xp_reset": "",
            "timezone": "UTC"
        }
def award_xp(user_id, amount):
    ensure_user(user_id)
    active = xp_data[user_id]["active"]
    if active:
        chars = xp_data[user_id]["characters"]
        if active in chars:
            chars[active]["xp"] += amount
        else:
            chars[active] = {"xp": amount}
    save_xp(xp_data)

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

@bot.command(name="sync")
async def sync(ctx):
    if not ctx.guild:
        await ctx.send("This command must be run in a server.")
        return

    guild = ctx.guild
    synced = await bot.tree.sync(guild=guild)
    await ctx.send(f"✅ Synced {len(synced)} commands to guild `{guild.name}` ({guild.id})")

@bot.event
async def on_ready():
    print(f"✅ {bot.user.name} is online.")

    env = os.getenv("ENV", "prod")
    guild_id = os.getenv("GUILD_ID")

    if env == "dev" and guild_id:
        print("🔧 Environment: development")
        guild = discord.Object(id=int(guild_id))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} slash commands to dev guild {guild_id}")
    else:
        print("🚀 Environment: production")
        synced = await bot.tree.sync()
        print(f"🌍 Synced {len(synced)} global slash commands")

    print("📦 Slash commands:")
    for cmd in bot.tree.get_commands():
        print(f" - /{cmd.name}")

# on_message() checks each message to see if it should be awarded RP or HF XP.
@bot.event
async def on_message(message):
    if message.author.bot and message.embeds and message.channel.id in xp_data.get("hf_channels", []):
        embed = message.embeds[0]
        title = embed.title.lower() if embed.title else ""
        description = embed.description.lower() if embed.description else ""
        field_texts = " ".join(f"{field.name.lower()} {field.value.lower()}" for field in embed.fields)
        combined_text = f"{title} {description} {field_texts}"

        print(f"📨 HF Embed Detected in #{getattr(message.channel, 'name', 'DM')} by {getattr(message.author, 'display_name', str(message.author))}")
        print(f"Title: {title}")
        print(f"Description: {description}")

        is_hunting = "goes hunting" in combined_text
        is_foraging = "goes foraging" in combined_text
        is_success = "time to harvest" in combined_text or "time to gut and harvest" in combined_text

        print(f"🧐 Hunting: {is_hunting}, Foraging: {is_foraging}, Success: {is_success}")

        if is_hunting or is_foraging:
            char_name = embed.title.split(" goes ")[0].strip().lower()
            print(f"🔍 Trying to match character name: '{char_name}'")

            matched_user_id = None
            for user_id, user_info in xp_data.items():
                if not isinstance(user_info, dict) or "characters" not in user_info:
                    continue
                for existing_char in user_info.get("characters", {}):
                    if existing_char.lower().startswith(char_name):
                        matched_user_id = user_id
                        break
                if matched_user_id:
                    break

            if not matched_user_id:
                print("❌ No matching user found for character name.")
                return

            ensure_user(matched_user_id)
            user_data = xp_data[matched_user_id]

            # Normalize char name
            matched_char_name = None
            for existing_char in user_data["characters"]:
                if existing_char.lower().startswith(char_name):
                    matched_char_name = existing_char
                    break

            if not matched_char_name:
                print("❌ Matched user found but character not found in user's list.")
                return

            char_data = user_data["characters"].get(matched_char_name, {})
            char_data.setdefault("xp", 0)
            char_data.setdefault("daily_hf", 0)

            if char_data["daily_hf"] >= xp_data.get("daily_hf_cap", 5):
                print(f"⚠️ Character '{matched_char_name}' has reached daily HF cap.")
                return

            base_xp = xp_data.get("hf_attempt_xp", 1)
            bonus = xp_data.get("hf_success_xp", 5) if is_success else 0
            xp_award = min(base_xp + bonus, xp_data["daily_hf_cap"] - char_data["daily_hf"])

            char_data["xp"] += xp_award
            char_data["daily_hf"] += xp_award
            user_data["characters"][matched_char_name] = char_data

            save_xp(xp_data)
            print(f"✅ Awarded {xp_award} XP to character '{matched_char_name}' (HF)")

    elif not message.author.bot and message.channel.id in xp_data.get("rp_channels", []):
        user_id = str(message.author.id)
        ensure_user(user_id)

        user_data = xp_data[user_id]
        now_utc = datetime.utcnow()
        tz = user_data.get("timezone", "UTC")
        try:
            user_time = now_utc.astimezone(ZoneInfo(tz))
        except:
            user_time = now_utc
        today = user_time.date().isoformat()

        if user_data.get("last_xp_reset") != today:
            for char in user_data["characters"].values():
                char["daily_xp"] = 0
                char["char_buffer"] = 0
                char["daily_hf"] = 0
            user_data["last_xp_reset"] = today

        active = user_data.get("active")
        if not active or active not in user_data.get("characters", {}):
            return

        char_data = user_data["characters"].get(active, {})
        char_data.setdefault("xp", 0)
        char_data.setdefault("daily_xp", 0)
        char_data.setdefault("char_buffer", 0)

        char_data["char_buffer"] += len(message.content)

        char_per_rp = xp_data.get("char_per_rp", 240)
        potential_xp = char_data["char_buffer"] // char_per_rp
        xp_remaining = xp_data.get("daily_rp_cap", 5) - char_data["daily_xp"]
        gained_xp = min(potential_xp, xp_remaining)

        char_data["char_buffer"] = char_data["char_buffer"] % char_per_rp

        if gained_xp > 0:
            char_data["xp"] += gained_xp
            char_data["daily_xp"] += gained_xp

        user_data["characters"][active] = char_data
        save_xp(xp_data)

    await bot.process_commands(message)

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
        msg = f"❌ Character '{char_name}' already exists."
    else:
        xp_data[user_id]["characters"][char_name] = {"xp": 0, "image_url": image_url or ""}
        xp_data[user_id]["active"] = char_name  # Always set the new one as active
        save_xp(xp_data)
        msg = f"✅ Character '{char_name}' created and set as active."
    await interaction.response.send_message(msg, ephemeral=True)

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

@bot.tree.command(name="xp_grant", description="Grant XP to a character")
@app_commands.describe(
    character_name="Name of the character to grant XP to",
    amount="Amount of XP to grant"
)
async def xp_grant(interaction: discord.Interaction, character_name: str, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
        return

    found_user = None
    found_char = None

    for user_id, user_data in xp_data.items():
        if not isinstance(user_data, dict):
            continue
        for name in user_data.get("characters", {}):
            if name.lower().startswith(character_name.lower()):
                found_user = user_id
                found_char = name
                break
        if found_user:
            break

    if not found_user or not found_char:
        await interaction.response.send_message("❌ Character not found.", ephemeral=True)
        return

    xp_data[found_user]["characters"][found_char]["xp"] += amount
    save_xp(xp_data)

    await interaction.response.send_message(
        f"✅ Granted {amount} XP to **{found_char}** (user ID: {found_user}).",
        ephemeral=True
    )

@bot.tree.command(name="xp_active", description="Set one of your characters as active")
@app_commands.describe(char_name="Name of the character to activate")
async def xp_active(interaction: discord.Interaction, char_name: str):
    user_id = str(interaction.user.id)
    ensure_user(user_id)

    chars = xp_data[user_id]["characters"]
    if not chars:
        await interaction.response.send_message("❌ You have no characters to activate.", ephemeral=True)
        return

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

@bot.tree.command(name="xp_add_rp_channel")
@app_commands.describe(channel="Channel to enable for RP XP tracking")
async def xp_add_rp_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    cid = channel.id
    if cid not in xp_data["rp_channels"]:
        xp_data["rp_channels"].append(cid)
        save_xp(xp_data)
        await interaction.response.send_message(f"✅ Channel {channel.mention} added for RP XP tracking.", ephemeral=True)
    else:
        await interaction.response.send_message(f"ℹ️ Channel {channel.mention} already tracked for RP.", ephemeral=True)

@bot.tree.command(name="xp_remove_rp_channel")
@app_commands.describe(channel="Channel to disable RP tracking")
async def xp_remove_rp_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    if channel.id in xp_data["rp_channels"]:
        xp_data["rp_channels"].remove(channel.id)
        save_xp(xp_data)

    await interaction.response.send_message(f"🚫 RP XP tracking disabled in {channel.mention}.", ephemeral=True)

@bot.tree.command(name="xp_add_hf_channel")
@app_commands.describe(channel="Channel to enable for hunting/foraging XP tracking")
async def xp_add_hf_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    cid = channel.id
    if cid not in xp_data["hf_channels"]:
        xp_data["hf_channels"].append(cid)
        save_xp(xp_data)
        await interaction.response.send_message(f"✅ Channel {channel.mention} added for hunting/foraging XP tracking.", ephemeral=True)
    else:
        await interaction.response.send_message(f"ℹ️ Channel {channel.mention} already tracked for HF.", ephemeral=True)

@bot.tree.command(name="xp_remove_hf_channel")
@app_commands.describe(channel="Channel to disable HF tracking")
async def xp_remove_rp_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    if channel.id in xp_data["hf_channels"]:
        xp_data["hf_channels"].remove(channel.id)
        save_xp(xp_data)

    await interaction.response.send_message(f"🚫 HF XP tracking disabled in {channel.mention}.", ephemeral=True)

@bot.tree.command(name="xp_config_hf")
@app_commands.describe(attempt_xp="XP per attempt", success_xp="XP per success", daily_cap="Max XP from HF per day")
async def xp_config_hf(interaction: discord.Interaction, attempt_xp: int, success_xp: int, daily_cap: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    xp_data["hf_attempt_xp"] = attempt_xp
    xp_data["hf_success_xp"] = success_xp
    xp_data["daily_hf_cap"] = daily_cap
    save_xp(xp_data)
    await interaction.response.send_message(
        f"✅ HF XP updated: {attempt_xp}/attempt, {success_xp}/success, daily cap: {daily_cap}.", ephemeral=True
    )

@bot.tree.command(name="xp_tracking")
async def xp_tracking(interaction: discord.Interaction):
    channel_ids = xp_data.get("rp_channels", [])
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

    xp_data["daily_rp_cap"] = amount
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

@bot.tree.command(name="xp_sync")
async def xp_sync(interaction: discord.Interaction):
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    await interaction.response.send_message("🔁 Slash commands re-synced to this server.", ephemeral=True)

@bot.tree.command(name="xp_help")
async def xp_help(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 XP Bot Help", description="Slash commands to manage your XP and characters:")
    embed.add_field(name="/xp_create", value="Create a new character.", inline=False)
    embed.add_field(name="/xp_active", value="Set which character is active.", inline=False)
    embed.add_field(name="/xp", value="View your active or named character.", inline=False)
    embed.add_field(name="/xp_list", value="List all your characters.", inline=False)
    embed.add_field(name="/xp_delete", value="Delete a character.", inline=False)
    embed.add_field(name="/xp_enable / /xp_disable", value="Enable or disable XP tracking in a channel.", inline=False)
    embed.add_field(name="/xp_tracking", value="List channels where XP tracking is enabled.", inline=False)
    embed.add_field(name="/xp_set_cap", value="(Admin) Set the daily XP cap.", inline=False)
    embed.add_field(name="/xp_set_timezone", value="Set your personal XP reset timezone.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# UI components
class XPSettingsModal(discord.ui.Modal, title="Configure RP Settings"):
    char_per_rp = discord.ui.TextInput(label="Characters per XP (RP)", placeholder="240", required=True)
    daily_rp_cap = discord.ui.TextInput(label="Daily RP XP Cap", placeholder="5", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp_data["char_per_rp"] = int(self.char_per_rp.value)
            xp_data["daily_rp_cap"] = int(self.daily_rp_cap.value)
            save_xp(xp_data)
            await interaction.response.send_message("✅ RP settings updated.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers.", ephemeral=True)

class HFSettingsModal(discord.ui.Modal, title="Configure HF Settings"):
    hf_attempt_xp = discord.ui.TextInput(label="XP per attempt", placeholder="1", required=True)
    hf_success_xp = discord.ui.TextInput(label="XP per success", placeholder="5", required=True)
    daily_hf_cap = discord.ui.TextInput(label="Daily HF XP Cap", placeholder="5", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp_data["hf_attempt_xp"] = int(self.hf_attempt_xp.value)
            xp_data["hf_success_xp"] = int(self.hf_success_xp.value)
            xp_data["daily_hf_cap"] = int(self.daily_hf_cap.value)
            save_xp(xp_data)
            await interaction.response.send_message("✅ HF settings updated.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers.", ephemeral=True)

class ChannelDropdown(discord.ui.Select):
    def __init__(self, label, target_key):
        self.target_key = target_key
        options = [
            discord.SelectOption(label=ch.name, value=str(ch.id))
            for ch in bot.get_all_channels() if isinstance(ch, discord.TextChannel)
        ]
        super().__init__(
            placeholder=f"Select {label} channels...",
            min_values=0,
            max_values=min(25, len(options)),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        xp_data[self.target_key] = [int(v) for v in self.values]
        save_xp(xp_data)
        await interaction.response.send_message(f"✅ Updated `{self.target_key}`.", ephemeral=True)

class ChannelSettingsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ChannelDropdown("RP", "rp_channels"))
        self.add_item(ChannelDropdown("HF", "hf_channels"))

class XPSettingsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="RP Settings", style=discord.ButtonStyle.primary)
    async def rp_settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(XPSettingsModal())

    @discord.ui.button(label="HF Settings", style=discord.ButtonStyle.primary)
    async def hf_settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HFSettingsModal())

    @discord.ui.button(label="Channel Settings", style=discord.ButtonStyle.secondary)
    async def channel_settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Choose channels to enable XP tracking:", view=ChannelSettingsView(), ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Settings view closed.", ephemeral=True)
        self.stop()

@bot.command(name="xpsettings")
async def xpsettings(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only.")
        return

    rp_channels = ", ".join(f"<#{cid}>" for cid in xp_data.get("rp_channels", [])) or "None"
    hf_channels = ", ".join(f"<#{cid}>" for cid in xp_data.get("hf_channels", [])) or "None"

    embed = discord.Embed(title="XP Bot Settings Overview")
    embed.add_field(name="RP Settings", value=f"Channels: {rp_channels}\nChars per XP: {xp_data['char_per_rp']}\nDaily RP Cap: {xp_data['daily_rp_cap']}", inline=False)
    embed.add_field(name="HF Settings", value=f"Channels: {hf_channels}\nXP per Attempt: {xp_data['hf_attempt_xp']}\nXP per Success: {xp_data['hf_success_xp']}\nDaily HF Cap: {xp_data['daily_hf_cap']}", inline=False)

    await ctx.send(embed=embed, view=XPSettingsView())

# Ignore unknown commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unknown commands
    else:
        raise error

if __name__ == "__main__":
    bot.run(TOKEN)
