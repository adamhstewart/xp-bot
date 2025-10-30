"""
Admin commands for XP Bot - channel management and configuration
"""
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.validation import validate_xp_amount, validate_daily_cap
from ui.views import XPSettingsView

logger = logging.getLogger('xp-bot')


def setup_admin_commands(bot, db, guild_id):
    """Register admin commands"""

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

    @bot.tree.command(name="xp_add_rp_channel")
    @app_commands.describe(channel="Channel to enable for RP XP tracking")
    @app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
    async def xp_add_rp_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await db.add_rp_channel(guild_id, channel.id)
        await interaction.response.send_message(f"✅ Channel {channel.mention} added for RP XP tracking.", ephemeral=True)

    @bot.tree.command(name="xp_remove_rp_channel")
    @app_commands.describe(channel="Channel to disable RP tracking")
    @app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
    async def xp_remove_rp_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await db.remove_rp_channel(guild_id, channel.id)
        await interaction.response.send_message(f"🚫 RP XP tracking disabled in {channel.mention}.", ephemeral=True)

    @bot.tree.command(name="xp_add_hf_channel")
    @app_commands.describe(channel="Channel to enable for hunting/foraging XP tracking")
    @app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
    async def xp_add_hf_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await db.add_hf_channel(guild_id, channel.id)
        await interaction.response.send_message(f"✅ Channel {channel.mention} added for hunting/foraging XP tracking.", ephemeral=True)

    @bot.tree.command(name="xp_remove_hf_channel")
    @app_commands.describe(channel="Channel to disable HF tracking")
    @app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
    async def xp_remove_hf_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await db.remove_hf_channel(guild_id, channel.id)
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
            guild_id,
            hf_attempt_xp=attempt_xp,
            hf_success_xp=success_xp,
            daily_hf_cap=daily_cap
        )
        await interaction.response.send_message(
            f"✅ HF XP updated: {attempt_xp}/attempt, {success_xp}/success, daily cap: {daily_cap}.", ephemeral=True
        )

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

        await db.update_config(guild_id, daily_rp_cap=amount)
        await interaction.response.send_message(f"✅ Daily XP cap set to {amount}.", ephemeral=True)

    @bot.command(name="xpsettings")
    async def xpsettings(ctx):
        """Legacy prefix command for XP settings UI"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Admin only.")
            return

        config = await db.get_config(guild_id)
        rp_channels = ", ".join(f"<#{cid}>" for cid in config.get("rp_channels", [])) or "None"
        hf_channels = ", ".join(f"<#{cid}>" for cid in config.get("hf_channels", [])) or "None"

        embed = discord.Embed(title="XP Bot Settings Overview")
        embed.add_field(name="RP Settings", value=f"Channels: {rp_channels}\nChars per XP: {config['char_per_rp']}\nDaily RP Cap: {config['daily_rp_cap']}", inline=False)
        embed.add_field(name="HF Settings", value=f"Channels: {hf_channels}\nXP per Attempt: {config['hf_attempt_xp']}\nXP per Success: {config['hf_success_xp']}\nDaily HF Cap: {config['daily_hf_cap']}", inline=False)

        await ctx.send(embed=embed, view=XPSettingsView(bot, db, guild_id))

    @bot.command(name="sync")
    async def sync(ctx):
        """Sync slash commands to the guild (legacy prefix command)"""
        if not ctx.guild:
            await ctx.send("This command must be run in a server.")
            return

        guild = ctx.guild
        synced = await bot.tree.sync(guild=guild)
        await ctx.send(f"✅ Synced {len(synced)} commands to guild `{guild.name}` ({guild.id})")
