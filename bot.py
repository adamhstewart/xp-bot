import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones
import difflib
import discord
from discord.ext import commands
from discord import app_commands
from database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.getenv("ENV") == "prod" else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('xp-bot')

# Reduce discord.py logging noise
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.INFO)

GUILD_ID = int(os.getenv("GUILD_ID", 0))
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Initialize database
db = Database()

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

# Validation constants
MAX_CHARACTER_NAME_LENGTH = 100
MIN_CHARACTER_NAME_LENGTH = 1
MAX_XP_GRANT = 1000000  # 1 million max XP per grant
MIN_XP_GRANT = -100000  # Allow removing up to 100k XP
MAX_DAILY_CAP = 1000
MIN_DAILY_CAP = 1
MAX_CHAR_PER_RP = 10000
MIN_CHAR_PER_RP = 1

def has_role(user, allowed_roles):
    """Return True if user has at least one allowed role name."""
    return any(role.name in allowed_roles for role in getattr(user, 'roles', []))

def validate_character_name(name: str) -> tuple[bool, str]:
    """
    Validate character name.
    Returns (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Character name cannot be empty."

    name = name.strip()

    if len(name) < MIN_CHARACTER_NAME_LENGTH:
        return False, f"Character name must be at least {MIN_CHARACTER_NAME_LENGTH} character."

    if len(name) > MAX_CHARACTER_NAME_LENGTH:
        return False, f"Character name cannot exceed {MAX_CHARACTER_NAME_LENGTH} characters."

    # Check for valid characters (alphanumeric, spaces, basic punctuation)
    import re
    if not re.match(r'^[a-zA-Z0-9\s\-\'\.]+$', name):
        return False, "Character name can only contain letters, numbers, spaces, hyphens, apostrophes, and periods."

    return True, ""

def validate_xp_amount(amount: int, allow_negative: bool = False) -> tuple[bool, str]:
    """
    Validate XP amount.
    Returns (is_valid, error_message)
    """
    if not allow_negative and amount < 0:
        return False, "XP amount cannot be negative."

    if amount < MIN_XP_GRANT:
        return False, f"XP amount cannot be less than {MIN_XP_GRANT}."

    if amount > MAX_XP_GRANT:
        return False, f"XP amount cannot exceed {MAX_XP_GRANT:,}."

    return True, ""

def validate_daily_cap(cap: int) -> tuple[bool, str]:
    """
    Validate daily cap value.
    Returns (is_valid, error_message)
    """
    if cap < MIN_DAILY_CAP:
        return False, f"Daily cap must be at least {MIN_DAILY_CAP}."

    if cap > MAX_DAILY_CAP:
        return False, f"Daily cap cannot exceed {MAX_DAILY_CAP}."

    return True, ""

def validate_char_per_rp(amount: int) -> tuple[bool, str]:
    """
    Validate characters per RP XP value.
    Returns (is_valid, error_message)
    """
    if amount < MIN_CHAR_PER_RP:
        return False, f"Characters per XP must be at least {MIN_CHAR_PER_RP}."

    if amount > MAX_CHAR_PER_RP:
        return False, f"Characters per XP cannot exceed {MAX_CHAR_PER_RP}."

    return True, ""

def validate_timezone(tz_string: str) -> tuple[bool, str]:
    """
    Validate timezone string.
    Returns (is_valid, error_message)
    """
    try:
        ZoneInfo(tz_string)
        return True, ""
    except Exception:
        return False, f"Invalid timezone '{tz_string}'. Use format like 'America/New_York' or 'UTC'."

def validate_image_url(url: str) -> tuple[bool, str]:
    """
    Validate image URL (basic validation).
    Returns (is_valid, error_message)
    """
    if not url:
        return True, ""  # Optional field

    import re
    # Basic URL pattern
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        return False, "Invalid URL format. Must start with http:// or https://"

    if len(url) > 2000:
        return False, "URL is too long (max 2000 characters)."

    return True, ""

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

async def should_reset_xp(user_id: int):
    """Check if user needs daily XP reset"""
    now_utc = datetime.utcnow()
    tz = await db.get_user_timezone(user_id)
    try:
        user_time = now_utc.astimezone(ZoneInfo(tz))
    except Exception:
        user_time = now_utc
    today_local = user_time.date()

    last_reset = await db.get_last_xp_reset(user_id)
    return last_reset != today_local

async def perform_daily_reset(user_id: int):
    """Perform daily reset for a user"""
    await db.reset_daily_caps(user_id)

    now_utc = datetime.utcnow()
    tz = await db.get_user_timezone(user_id)
    try:
        user_time = now_utc.astimezone(ZoneInfo(tz))
    except Exception:
        user_time = now_utc

    await db.update_last_xp_reset(user_id, user_time.date())

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
    logger.info(f"Bot '{bot.user.name}' is online")

    # Connect to database
    await db.connect()
    await db.initialize_schema()

    env = os.getenv("ENV", "prod")
    guild_id = os.getenv("GUILD_ID")

    if env == "dev" and guild_id:
        logger.info("Environment: development")
        guild = discord.Object(id=int(guild_id))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info(f"Synced {len(synced)} slash commands to dev guild {guild_id}")
    else:
        logger.info("Environment: production")
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} global slash commands")

    logger.info("Available slash commands:")
    for cmd in bot.tree.get_commands():
        logger.info(f"  /{cmd.name}")

# on_message() checks each message to see if it should be awarded RP or HF XP.
@bot.event
async def on_message(message):
    config = await db.get_config(GUILD_ID)

    if message.author.bot and message.embeds and message.channel.id in config.get("hf_channels", []):
        embed = message.embeds[0]
        title = embed.title.lower() if embed.title else ""
        description = embed.description.lower() if embed.description else ""
        field_texts = " ".join(f"{field.name.lower()} {field.value.lower()}" for field in embed.fields)
        combined_text = f"{title} {description} {field_texts}"

        logger.debug(f"HF Embed detected in #{getattr(message.channel, 'name', 'DM')} by {getattr(message.author, 'display_name', str(message.author))}")
        logger.debug(f"Embed title: {title}")
        logger.debug(f"Embed description: {description}")

        is_hunting = "goes hunting" in combined_text
        is_foraging = "goes foraging" in combined_text
        is_success = "time to harvest" in combined_text or "time to gut and harvest" in combined_text

        logger.debug(f"Hunting: {is_hunting}, Foraging: {is_foraging}, Success: {is_success}")

        if is_hunting or is_foraging:
            char_name = embed.title.split(" goes ")[0].strip()
            logger.debug(f"Trying to match character name: '{char_name}'")

            # Find all characters with this name
            matches = await db.find_all_characters_by_name(char_name)

            if not matches:
                logger.warning(f"No matching character found for HF activity: '{char_name}'")
                return

            # Disambiguate if multiple matches
            if len(matches) == 1:
                user_id, char_data = matches[0]
                logger.debug(f"Single match found for '{char_name}': user {user_id}")
            else:
                logger.warning(f"Multiple characters named '{char_name}' found ({len(matches)} matches)")

                # Try to disambiguate using message mentions
                mentioned_user_ids = [mention.id for mention in message.mentions]

                if mentioned_user_ids:
                    logger.debug(f"Checking {len(mentioned_user_ids)} mentioned users for disambiguation")
                    matching_mentions = [(uid, cdata) for uid, cdata in matches if uid in mentioned_user_ids]

                    if len(matching_mentions) == 1:
                        user_id, char_data = matching_mentions[0]
                        logger.info(f"Disambiguated '{char_name}' using mention: user {user_id}")
                    elif len(matching_mentions) > 1:
                        logger.warning(f"Multiple mentioned users have characters named '{char_name}'. Skipping XP award.")
                        return
                    else:
                        logger.warning(f"No mentioned users have a character named '{char_name}'. Skipping XP award.")
                        return
                else:
                    # No mentions to help disambiguate
                    logger.warning(f"Cannot disambiguate character '{char_name}' - no user mentions in message. Skipping XP award.")
                    logger.debug(f"Conflicting user IDs: {[uid for uid, _ in matches]}")
                    return

            char_name_actual = char_data['name']

            # Check daily HF cap
            if char_data['daily_hf'] >= config.get('daily_hf_cap', 5):
                logger.debug(f"Character '{char_name_actual}' has reached daily HF cap")
                return

            # Calculate XP award
            base_xp = config.get('hf_attempt_xp', 1)
            bonus = config.get('hf_success_xp', 5) if is_success else 0
            xp_award = min(base_xp + bonus, config['daily_hf_cap'] - char_data['daily_hf'])

            # Award XP
            await db.award_xp(user_id, char_name_actual, xp_award, daily_hf_delta=xp_award)

            logger.info(f"Awarded {xp_award} HF XP to '{char_name_actual}' (user {user_id})")

    elif not message.author.bot and message.channel.id in config.get("rp_channels", []):
        user_id = message.author.id
        await db.ensure_user(user_id)

        # Check if we need to reset daily caps
        if await should_reset_xp(user_id):
            await perform_daily_reset(user_id)

        # Get active character
        active_char = await db.get_active_character(user_id)
        if not active_char:
            return

        # Add to character buffer
        char_buffer = active_char['char_buffer'] + len(message.content)

        # Calculate XP from buffer
        char_per_rp = config.get('char_per_rp', 240)
        potential_xp = char_buffer // char_per_rp
        xp_remaining = config.get('daily_rp_cap', 5) - active_char['daily_xp']
        gained_xp = min(potential_xp, xp_remaining)

        # Update buffer remainder
        new_buffer = char_buffer % char_per_rp

        # Award XP if any gained
        if gained_xp > 0:
            await db.award_xp(
                user_id,
                active_char['name'],
                gained_xp,
                daily_xp_delta=gained_xp,
                char_buffer_delta=new_buffer - active_char['char_buffer']
            )
        elif new_buffer != active_char['char_buffer']:
            # Just update buffer
            await db.update_character_buffer(user_id, active_char['name'], new_buffer)

    await bot.process_commands(message)

# SLASH COMMANDS
@bot.tree.command(name="xp", description="View XP, level, and progress for a character")
@app_commands.describe(char_name="Optional character name (defaults to active)")
@app_commands.checks.cooldown(3, 10.0, key=lambda i: i.user.id)
async def xp(interaction: discord.Interaction, char_name: str = None):
    user_id = interaction.user.id
    await db.ensure_user(user_id)

    characters = await db.list_characters(user_id)
    if not characters:
        await interaction.response.send_message("❌ You don't have any characters yet.", ephemeral=True)
        return

    if not char_name:
        active_char = await db.get_active_character(user_id)
        if not active_char:
            await interaction.response.send_message("❌ No active character. Use `/xp_active` to set one.", ephemeral=True)
            return
        char = active_char
    else:
        # Try exact match first
        char = await db.get_character(user_id, char_name)

        # If not found, try fuzzy match
        if not char:
            char_names = [c['name'] for c in characters]
            matches = difflib.get_close_matches(char_name, char_names, n=1, cutoff=0.6)
            if not matches:
                await interaction.response.send_message(f"❌ Character '{char_name}' not found.", ephemeral=True)
                return
            char = await db.get_character(user_id, matches[0])

    xp_amount = char["xp"]
    level, progress, required = get_level_and_progress(xp_amount)

    desc = f"XP: {xp_amount}\nLevel: {level}"
    if progress is not None:
        bar = int((progress / required) * 20)
        desc += f"\nProgress: `[{'█'*bar}{'-'*(20-bar)}] {progress}/{required}`"

    embed = discord.Embed(title=char['name'], description=desc)
    if char.get("image_url"):
        embed.set_image(url=char["image_url"])

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="xp_create", description="Create a new character")
@app_commands.describe(char_name="Character name", image_url="Optional image URL")
@app_commands.checks.cooldown(3, 60.0, key=lambda i: i.user.id)
async def xp_create(interaction: discord.Interaction, char_name: str, image_url: str = None):
    user_id = interaction.user.id

    # Validate character name
    is_valid, error_msg = validate_character_name(char_name)
    if not is_valid:
        await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
        logger.debug(f"Invalid character name '{char_name}' from user {user_id}: {error_msg}")
        return

    # Validate image URL if provided
    if image_url:
        is_valid, error_msg = validate_image_url(image_url)
        if not is_valid:
            await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
            logger.debug(f"Invalid image URL from user {user_id}: {error_msg}")
            return

    await db.ensure_user(user_id)

    # Check if character already exists
    char_name = char_name.strip()  # Use trimmed version
    existing = await db.get_character(user_id, char_name)
    if existing:
        await interaction.response.send_message(f"❌ Character '{char_name}' already exists.", ephemeral=True)
        return

    # Create character
    try:
        await db.create_character(user_id, char_name, image_url)
        await interaction.response.send_message(f"✅ Character '{char_name}' created and set as active.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error creating character '{char_name}' for user {user_id}: {e}")
        await interaction.response.send_message(f"❌ Error creating character: {str(e)}", ephemeral=True)

@bot.tree.command(name="xp_delete")
@app_commands.describe(name="Character name to delete")
@app_commands.checks.cooldown(2, 60.0, key=lambda i: i.user.id)
async def xp_delete(interaction: discord.Interaction, name: str):
    user_id = interaction.user.id
    await db.ensure_user(user_id)

    deleted = await db.delete_character(user_id, name)
    if not deleted:
        await interaction.response.send_message("❌ Character not found.", ephemeral=True)
        return

    await interaction.response.send_message(f"🗑️ Deleted character '{name}'.", ephemeral=True)

@bot.tree.command(name="xp_grant", description="Grant XP to a character")
@app_commands.describe(
    character_name="Name of the character to grant XP to",
    amount="Amount of XP to grant"
)
@app_commands.checks.cooldown(10, 60.0, key=lambda i: i.user.id)
async def xp_grant(interaction: discord.Interaction, character_name: str, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
        return

    # Validate XP amount (allow negative for removing XP)
    is_valid, error_msg = validate_xp_amount(amount, allow_negative=True)
    if not is_valid:
        await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
        logger.debug(f"Invalid XP amount {amount} from admin {interaction.user.id}")
        return

    # Find character across all users
    result = await db.find_character_by_name_any_user(character_name)

    if not result:
        await interaction.response.send_message("❌ Character not found.", ephemeral=True)
        return

    user_id, char_data = result
    char_name = char_data['name']

    # Award XP (bypassing daily caps since this is admin grant)
    await db.award_xp(user_id, char_name, amount)

    action = "Granted" if amount >= 0 else "Removed"
    await interaction.response.send_message(
        f"✅ {action} {abs(amount)} XP {'to' if amount >= 0 else 'from'} **{char_name}** (user ID: {user_id}).",
        ephemeral=True
    )

@bot.tree.command(name="xp_active", description="Set one of your characters as active")
@app_commands.describe(char_name="Name of the character to activate")
@app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
async def xp_active(interaction: discord.Interaction, char_name: str):
    user_id = interaction.user.id
    await db.ensure_user(user_id)

    chars = await db.list_characters(user_id)
    if not chars:
        await interaction.response.send_message("❌ You have no characters to activate.", ephemeral=True)
        return

    # Try exact match first
    char_names = [c['name'] for c in chars]
    matched_name = char_name

    if char_name not in char_names:
        # Try fuzzy match
        matches = difflib.get_close_matches(char_name, char_names, n=1, cutoff=0.6)
        if not matches:
            await interaction.response.send_message(f"❌ No character found matching '{char_name}'.", ephemeral=True)
            return
        matched_name = matches[0]

    # Set as active
    await db.set_active_character(user_id, matched_name)
    await interaction.response.send_message(f"🟢 '{matched_name}' is now your active character.", ephemeral=True)

@bot.tree.command(name="xp_list")
@app_commands.checks.cooldown(3, 30.0, key=lambda i: i.user.id)
async def xp_list(interaction: discord.Interaction):
    user_id = interaction.user.id
    await db.ensure_user(user_id)

    chars = await db.list_characters(user_id)
    active_char = await db.get_active_character(user_id)
    active_name = active_char['name'] if active_char else None

    if not chars:
        await interaction.response.send_message("You have no characters.", ephemeral=True)
        return

    lines = []
    for char in chars:
        mark = "🟢" if char['name'] == active_name else "⚪"
        lines.append(f"{mark} {char['name']} — {char['xp']} XP")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@bot.tree.command(name="xp_add_rp_channel")
@app_commands.describe(channel="Channel to enable for RP XP tracking")
@app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
async def xp_add_rp_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    await db.add_rp_channel(GUILD_ID, channel.id)
    await interaction.response.send_message(f"✅ Channel {channel.mention} added for RP XP tracking.", ephemeral=True)

@bot.tree.command(name="xp_remove_rp_channel")
@app_commands.describe(channel="Channel to disable RP tracking")
@app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
async def xp_remove_rp_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    await db.remove_rp_channel(GUILD_ID, channel.id)
    await interaction.response.send_message(f"🚫 RP XP tracking disabled in {channel.mention}.", ephemeral=True)

@bot.tree.command(name="xp_add_hf_channel")
@app_commands.describe(channel="Channel to enable for hunting/foraging XP tracking")
@app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
async def xp_add_hf_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    await db.add_hf_channel(GUILD_ID, channel.id)
    await interaction.response.send_message(f"✅ Channel {channel.mention} added for hunting/foraging XP tracking.", ephemeral=True)

@bot.tree.command(name="xp_remove_hf_channel")
@app_commands.describe(channel="Channel to disable HF tracking")
@app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
async def xp_remove_hf_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    await db.remove_hf_channel(GUILD_ID, channel.id)
    await interaction.response.send_message(f"🚫 HF XP tracking disabled in {channel.mention}.", ephemeral=True)

@bot.tree.command(name="xp_config_hf")
@app_commands.describe(attempt_xp="XP per attempt", success_xp="XP per success", daily_cap="Max XP from HF per day")
@app_commands.checks.cooldown(3, 60.0, key=lambda i: i.user.id)
async def xp_config_hf(interaction: discord.Interaction, attempt_xp: int, success_xp: int, daily_cap: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    # Validate XP amounts (must be non-negative)
    is_valid, error_msg = validate_xp_amount(attempt_xp)
    if not is_valid:
        await interaction.response.send_message(f"❌ Attempt XP: {error_msg}", ephemeral=True)
        return

    is_valid, error_msg = validate_xp_amount(success_xp)
    if not is_valid:
        await interaction.response.send_message(f"❌ Success XP: {error_msg}", ephemeral=True)
        return

    # Validate daily cap
    is_valid, error_msg = validate_daily_cap(daily_cap)
    if not is_valid:
        await interaction.response.send_message(f"❌ Daily cap: {error_msg}", ephemeral=True)
        return

    await db.update_config(
        GUILD_ID,
        hf_attempt_xp=attempt_xp,
        hf_success_xp=success_xp,
        daily_hf_cap=daily_cap
    )
    await interaction.response.send_message(
        f"✅ HF XP updated: {attempt_xp}/attempt, {success_xp}/success, daily cap: {daily_cap}.", ephemeral=True
    )

@bot.tree.command(name="xp_tracking")
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
async def xp_tracking(interaction: discord.Interaction):
    config = await db.get_config(GUILD_ID)
    channel_ids = config.get("rp_channels", [])

    if not channel_ids:
        await interaction.response.send_message("No channels have XP tracking enabled.", ephemeral=True)
        return

    mentions = [f"<#{cid}>" for cid in channel_ids]
    await interaction.response.send_message("📍 XP is tracked in:\n" + "\n".join(mentions), ephemeral=True)

@bot.tree.command(name="xp_set_cap")
@app_commands.describe(amount="New daily XP cap")
@app_commands.checks.cooldown(3, 60.0, key=lambda i: i.user.id)
async def xp_set_cap(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    # Validate daily cap
    is_valid, error_msg = validate_daily_cap(amount)
    if not is_valid:
        await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
        logger.debug(f"Invalid daily cap {amount} from admin {interaction.user.id}")
        return

    await db.update_config(GUILD_ID, daily_rp_cap=amount)
    await interaction.response.send_message(f"✅ Daily XP cap set to {amount}.", ephemeral=True)

@bot.tree.command(name="xp_set_timezone")
@app_commands.describe(timezone="Your timezone, e.g. America/New_York")
@app_commands.checks.cooldown(1, 300.0, key=lambda i: i.user.id)
async def xp_set_timezone(interaction: discord.Interaction, timezone: str):
    user_id = interaction.user.id

    # Validate timezone
    is_valid, error_msg = validate_timezone(timezone)
    if not is_valid:
        await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
        logger.debug(f"Invalid timezone '{timezone}' from user {user_id}")
        return

    await db.ensure_user(user_id)
    await db.set_user_timezone(user_id, timezone)
    await interaction.response.send_message(f"✅ Timezone set to {timezone}.", ephemeral=True)

@bot.tree.command(name="xp_sync")
@app_commands.checks.cooldown(1, 300.0, key=lambda i: i.user.id)
async def xp_sync(interaction: discord.Interaction):
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    await interaction.response.send_message("🔁 Slash commands re-synced to this server.", ephemeral=True)

@bot.tree.command(name="xp_help")
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
async def xp_help(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 XP Bot Help", description="Slash commands to manage your XP and characters:")
    embed.add_field(name="/xp_create", value="Create a new character.", inline=False)
    embed.add_field(name="/xp_active", value="Set which character is active.", inline=False)
    embed.add_field(name="/xp", value="View your active or named character.", inline=False)
    embed.add_field(name="/xp_list", value="List all your characters.", inline=False)
    embed.add_field(name="/xp_delete", value="Delete a character.", inline=False)
    embed.add_field(name="/xp_add_rp_channel / /xp_remove_rp_channel", value="Enable or disable RP XP tracking in a channel.", inline=False)
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
            char_per_rp_val = int(self.char_per_rp.value)
            daily_rp_cap_val = int(self.daily_rp_cap.value)

            # Validate char_per_rp
            is_valid, error_msg = validate_char_per_rp(char_per_rp_val)
            if not is_valid:
                await interaction.response.send_message(f"❌ Characters per XP: {error_msg}", ephemeral=True)
                return

            # Validate daily_rp_cap
            is_valid, error_msg = validate_daily_cap(daily_rp_cap_val)
            if not is_valid:
                await interaction.response.send_message(f"❌ Daily RP cap: {error_msg}", ephemeral=True)
                return

            await db.update_config(
                GUILD_ID,
                char_per_rp=char_per_rp_val,
                daily_rp_cap=daily_rp_cap_val
            )
            await interaction.response.send_message("✅ RP settings updated.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers.", ephemeral=True)

class HFSettingsModal(discord.ui.Modal, title="Configure HF Settings"):
    hf_attempt_xp = discord.ui.TextInput(label="XP per attempt", placeholder="1", required=True)
    hf_success_xp = discord.ui.TextInput(label="XP per success", placeholder="5", required=True)
    daily_hf_cap = discord.ui.TextInput(label="Daily HF XP Cap", placeholder="5", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            attempt_xp = int(self.hf_attempt_xp.value)
            success_xp = int(self.hf_success_xp.value)
            daily_cap = int(self.daily_hf_cap.value)

            # Validate attempt XP
            is_valid, error_msg = validate_xp_amount(attempt_xp)
            if not is_valid:
                await interaction.response.send_message(f"❌ Attempt XP: {error_msg}", ephemeral=True)
                return

            # Validate success XP
            is_valid, error_msg = validate_xp_amount(success_xp)
            if not is_valid:
                await interaction.response.send_message(f"❌ Success XP: {error_msg}", ephemeral=True)
                return

            # Validate daily cap
            is_valid, error_msg = validate_daily_cap(daily_cap)
            if not is_valid:
                await interaction.response.send_message(f"❌ Daily cap: {error_msg}", ephemeral=True)
                return

            await db.update_config(
                GUILD_ID,
                hf_attempt_xp=attempt_xp,
                hf_success_xp=success_xp,
                daily_hf_cap=daily_cap
            )
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
        channel_ids = [int(v) for v in self.values]
        if self.target_key == "rp_channels":
            await db.update_config(GUILD_ID, rp_channels=channel_ids)
        elif self.target_key == "hf_channels":
            await db.update_config(GUILD_ID, hf_channels=channel_ids)
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

    config = await db.get_config(GUILD_ID)
    rp_channels = ", ".join(f"<#{cid}>" for cid in config.get("rp_channels", [])) or "None"
    hf_channels = ", ".join(f"<#{cid}>" for cid in config.get("hf_channels", [])) or "None"

    embed = discord.Embed(title="XP Bot Settings Overview")
    embed.add_field(name="RP Settings", value=f"Channels: {rp_channels}\nChars per XP: {config['char_per_rp']}\nDaily RP Cap: {config['daily_rp_cap']}", inline=False)
    embed.add_field(name="HF Settings", value=f"Channels: {hf_channels}\nXP per Attempt: {config['hf_attempt_xp']}\nXP per Success: {config['hf_success_xp']}\nDaily HF Cap: {config['daily_hf_cap']}", inline=False)

    await ctx.send(embed=embed, view=XPSettingsView())

# Error handlers
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle errors from slash commands"""
    if isinstance(error, app_commands.CommandOnCooldown):
        # Rate limit hit
        minutes, seconds = divmod(int(error.retry_after), 60)
        if minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"

        await interaction.response.send_message(
            f"⏱️ Slow down! You can use this command again in **{time_str}**.",
            ephemeral=True
        )
        logger.debug(f"Rate limit hit by user {interaction.user.id} on /{interaction.command.name}")
    elif isinstance(error, app_commands.CheckFailure):
        # Permission check failed or other check
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.",
            ephemeral=True
        )
        logger.warning(f"Permission denied for user {interaction.user.id} on /{interaction.command.name}")
    else:
        # Other errors - log and show generic message
        logger.error(f"Error in /{interaction.command.name}: {error}", exc_info=True)
        try:
            await interaction.response.send_message(
                "❌ An error occurred while processing your command. Please try again later.",
                ephemeral=True
            )
        except:
            # Response already sent, try followup
            try:
                await interaction.followup.send(
                    "❌ An error occurred while processing your command.",
                    ephemeral=True
                )
            except:
                pass  # Nothing we can do

@bot.event
async def on_command_error(ctx, error):
    """Handle errors from traditional prefix commands"""
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unknown commands
    else:
        logger.error(f"Error in !{ctx.command}: {error}", exc_info=True)
        raise error

if __name__ == "__main__":
    bot.run(TOKEN)
