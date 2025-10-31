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

    async def has_character_creation_permission(interaction: discord.Interaction) -> bool:
        """Check if user has permission to create characters (same for granting XP)"""
        # Admins always have permission
        if interaction.user.guild_permissions.administrator:
            return True

        # Check if user has any of the allowed roles
        allowed_role_ids = await db.get_character_creation_roles(guild_id)

        # If no roles configured, allow everyone
        if not allowed_role_ids:
            return True

        # Check if user has any allowed role
        user_role_ids = [role.id for role in interaction.user.roles]
        return any(role_id in allowed_role_ids for role_id in user_role_ids)

    async def all_characters_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete function for all character names (admin command)"""
        try:
            # Search all characters across all users
            char_names = await db.search_all_character_names(current, limit=25)
            return [
                app_commands.Choice(name=name, value=name)
                for name in char_names
            ]
        except Exception as e:
            logger.error(f"Error in all characters autocomplete: {e}")
            return []

    @bot.tree.command(name="xp_grant", description="Grant XP to a character")
    @app_commands.describe(
        character_name="Name of the character to grant XP to",
        amount="Amount of XP to grant",
        memo="Reason for granting XP (optional)"
    )
    @app_commands.autocomplete(character_name=all_characters_autocomplete)
    @app_commands.checks.cooldown(10, 60.0, key=lambda i: i.user.id)
    async def xp_grant(interaction: discord.Interaction, character_name: str, amount: int, memo: str = None):
        # Check if user has permission to grant XP (same as character creation)
        if not await has_character_creation_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to grant XP. Contact an administrator.",
                ephemeral=True
            )
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
        character_id = char_data['id']

        # Award XP (bypassing daily caps since this is admin grant)
        await db.award_xp(user_id, char_name, amount)

        # Log the XP grant with memo
        await db.log_xp_grant(character_id, interaction.user.id, amount, memo)

        # Get updated character info for notification
        from utils.xp import get_level_and_progress
        updated_char = await db.get_character(user_id, char_name)
        new_xp = updated_char['xp']
        new_level, progress, required = get_level_and_progress(new_xp)

        # Post notification to request channel if configured
        request_channel_id = await db.get_xp_request_channel(guild_id)
        if request_channel_id:
            request_channel = bot.get_channel(request_channel_id)
            if request_channel:
                try:
                    from ui.character_view import DEFAULT_CHARACTER_IMAGE
                    notification_embed = discord.Embed(
                        title=f"XP Granted - {char_name}",
                        color=discord.Color.green() if amount >= 0 else discord.Color.orange(),
                        timestamp=discord.utils.utcnow()
                    )

                    notification_embed.add_field(
                        name="**Player**",
                        value=f"<@{user_id}>",
                        inline=False
                    )

                    notification_embed.add_field(
                        name="**New Level**",
                        value=str(new_level),
                        inline=True
                    )

                    notification_embed.add_field(
                        name="**New Total XP**",
                        value=f"{new_xp:,}",
                        inline=True
                    )

                    action_word = "Granted" if amount >= 0 else "Removed"
                    notification_embed.add_field(
                        name=f"**Amount {action_word}**",
                        value=f"{abs(amount):,} XP",
                        inline=False
                    )

                    if progress is not None:
                        percentage = int((progress / required) * 100)
                        bar = int((progress / required) * 20)
                        progress_text = f"`[{'█'*bar}{'-'*(20-bar)}]` {progress}/{required} ({percentage}%)"
                        notification_embed.add_field(
                            name="**Current Level Progress**",
                            value=progress_text,
                            inline=False
                        )

                    if memo:
                        notification_embed.add_field(
                            name="**Reason**",
                            value=memo,
                            inline=False
                        )

                    # Add character image
                    image_url = updated_char.get("image_url") or DEFAULT_CHARACTER_IMAGE
                    notification_embed.set_thumbnail(url=image_url)

                    notification_embed.set_footer(text=f"Granted by {interaction.user.display_name}")

                    await request_channel.send(embed=notification_embed)
                except Exception as e:
                    logger.error(f"Failed to post XP grant notification: {e}")

        action = "Granted" if amount >= 0 else "Removed"
        response = f"✅ {action} {abs(amount)} XP {'to' if amount >= 0 else 'from'} **{char_name}** (user ID: {user_id})."
        if memo:
            response += f"\nMemo: {memo}"

        await interaction.response.send_message(response, ephemeral=True)

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

    @bot.tree.command(name="xp_add_creator_role", description="Add a role that can create characters")
    @app_commands.describe(role="Role to grant character creation permissions")
    @app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
    async def xp_add_creator_role(interaction: discord.Interaction, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await db.add_character_creation_role(guild_id, role.id)
        await interaction.response.send_message(
            f"✅ Role {role.mention} can now create characters.",
            ephemeral=True
        )

    @bot.tree.command(name="xp_remove_creator_role", description="Remove character creation permissions from a role")
    @app_commands.describe(role="Role to remove character creation permissions from")
    @app_commands.checks.cooldown(5, 60.0, key=lambda i: i.user.id)
    async def xp_remove_creator_role(interaction: discord.Interaction, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await db.remove_character_creation_role(guild_id, role.id)
        await interaction.response.send_message(
            f"🚫 Role {role.mention} can no longer create characters.",
            ephemeral=True
        )

    @bot.tree.command(name="xp_list_creator_roles", description="List roles that can create characters")
    @app_commands.checks.cooldown(3, 30.0, key=lambda i: i.user.id)
    async def xp_list_creator_roles(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        role_ids = await db.get_character_creation_roles(guild_id)

        if not role_ids:
            await interaction.response.send_message(
                "No roles configured. Use `/xp_add_creator_role` to add roles that can create characters.",
                ephemeral=True
            )
            return

        role_mentions = [f"<@&{rid}>" for rid in role_ids]
        await interaction.response.send_message(
            f"**Roles that can create characters:**\n" + "\n".join(role_mentions),
            ephemeral=True
        )

    @bot.tree.command(name="xp_set_request_channel", description="Set channel for XP requests")
    @app_commands.describe(channel="Channel where XP requests will be posted")
    @app_commands.checks.cooldown(3, 60.0, key=lambda i: i.user.id)
    async def xp_set_request_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await db.set_xp_request_channel(guild_id, channel.id)
        await interaction.response.send_message(
            f"✅ XP requests will now be posted in {channel.mention}.",
            ephemeral=True
        )

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
