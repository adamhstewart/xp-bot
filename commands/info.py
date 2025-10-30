"""
Informational commands for XP Bot
"""
import logging
import discord
from discord import app_commands
from utils.validation import validate_timezone

logger = logging.getLogger('xp-bot')


def setup_info_commands(bot, db, guild_id):
    """Register informational commands"""

    @bot.tree.command(name="xp_tracking")
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
    async def xp_tracking(interaction: discord.Interaction):
        """Show which channels have XP tracking enabled"""
        config = await db.get_config(guild_id)
        channel_ids = config.get("rp_channels", [])

        if not channel_ids:
            await interaction.response.send_message("No channels have XP tracking enabled.", ephemeral=True)
            return

        mentions = [f"<#{cid}>" for cid in channel_ids]
        await interaction.response.send_message("📍 XP is tracked in:\n" + "\n".join(mentions), ephemeral=True)

    @bot.tree.command(name="xp_set_timezone")
    @app_commands.describe(timezone="Your timezone, e.g. America/New_York")
    @app_commands.checks.cooldown(1, 300.0, key=lambda i: i.user.id)
    async def xp_set_timezone(interaction: discord.Interaction, timezone: str):
        """Set your personal timezone for daily XP resets"""
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
        """Re-sync slash commands to this server"""
        guild = discord.Object(id=guild_id)
        await bot.tree.sync(guild=guild)
        await interaction.response.send_message("🔁 Slash commands re-synced to this server.", ephemeral=True)

    @bot.tree.command(name="xp_help")
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
    async def xp_help(interaction: discord.Interaction):
        """Show help information for all XP Bot commands"""
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
