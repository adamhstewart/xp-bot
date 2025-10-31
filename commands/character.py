"""
Character management commands for XP Bot
"""
import logging
import difflib
import discord
from discord import app_commands
from utils.xp import get_level_and_progress
from utils.validation import validate_character_name, validate_image_url, validate_character_sheet_url
from utils.exceptions import (
    DatabaseError,
    CharacterNotFoundError,
    DuplicateCharacterError
)
from ui.character_view import CharacterNavigationView
from ui.xp_request_view import XPRequestView

logger = logging.getLogger('xp-bot')


def setup_character_commands(bot, db, guild_id):
    """Register character management commands"""

    async def has_character_creation_permission(interaction: discord.Interaction) -> bool:
        """Check if user has permission to create characters"""
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

    async def character_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete function for user's character names"""
        try:
            user_id = interaction.user.id
            await db.ensure_user(user_id)
            characters = await db.list_characters(user_id)

            # Filter characters based on what user is typing
            char_names = [char['name'] for char in characters]
            if current:
                # Case-insensitive filtering
                filtered = [name for name in char_names if current.lower() in name.lower()]
            else:
                filtered = char_names

            # Return up to 25 choices (Discord limit)
            return [
                app_commands.Choice(name=name, value=name)
                for name in filtered[:25]
            ]
        except Exception as e:
            logger.error(f"Error in character autocomplete: {e}")
            return []

    @bot.tree.command(name="xp", description="View XP, level, and progress for characters")
    @app_commands.describe(user="User whose characters to view (defaults to yourself)")
    @app_commands.checks.cooldown(3, 10.0, key=lambda i: i.user.id)
    async def xp(interaction: discord.Interaction, user: discord.User = None):
        # Default to viewing own characters
        if user is None:
            user = interaction.user

        target_user_id = user.id
        viewer_user_id = interaction.user.id
        await db.ensure_user(target_user_id)

        characters = await db.list_characters(target_user_id)
        if not characters:
            if target_user_id == viewer_user_id:
                await interaction.response.send_message("❌ You don't have any characters yet.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {user.display_name} doesn't have any characters yet.", ephemeral=True)
            return

        # Get active character name (only if viewing own characters)
        active_char_name = None
        if target_user_id == viewer_user_id:
            active_char = await db.get_active_character(target_user_id)
            active_char_name = active_char['name'] if active_char else None

        # Start at first character (or active if viewing own)
        current_index = 0
        if target_user_id == viewer_user_id and active_char_name:
            # Find active character index
            for i, char in enumerate(characters):
                if char['name'] == active_char_name:
                    current_index = i
                    break

        # Create navigation view
        view = CharacterNavigationView(target_user_id, viewer_user_id, characters, active_char_name, db, current_index)
        embed = view._create_embed()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @bot.tree.command(name="xp_create", description="Create a new character")
    @app_commands.describe(
        user="User to create character for (defaults to yourself)",
        char_name="Character name",
        sheet_url="Character sheet URL",
        image_url="Optional image URL"
    )
    @app_commands.checks.cooldown(3, 60.0, key=lambda i: i.user.id)
    async def xp_create(interaction: discord.Interaction, user: discord.User = None, char_name: str = "", sheet_url: str = "", image_url: str = None):
        # Check required fields
        if not char_name or not char_name.strip():
            await interaction.response.send_message("❌ Character name is required.", ephemeral=True)
            return

        if not sheet_url or not sheet_url.strip():
            await interaction.response.send_message("❌ Character sheet URL is required.", ephemeral=True)
            return

        # Check if user has permission to create characters
        if not await has_character_creation_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to create characters. Contact an administrator.",
                ephemeral=True
            )
            return

        # Default to creating for self
        if user is None:
            user = interaction.user

        target_user_id = user.id

        # Only admins can create characters for other users
        if target_user_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can create characters for other users.",
                ephemeral=True
            )
            return

        # Validate character name
        is_valid, error_msg = validate_character_name(char_name)
        if not is_valid:
            await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
            logger.debug(f"Invalid character name '{char_name}' from user {interaction.user.id}: {error_msg}")
            return

        # Validate image URL if provided
        if image_url:
            is_valid, error_msg = validate_image_url(image_url)
            if not is_valid:
                await interaction.response.send_message(f"❌ Image URL: {error_msg}", ephemeral=True)
                logger.debug(f"Invalid image URL from user {interaction.user.id}: {error_msg}")
                return

        # Validate character sheet URL (now required)
        is_valid, error_msg = validate_character_sheet_url(sheet_url)
        if not is_valid:
            await interaction.response.send_message(f"❌ Character sheet URL: {error_msg}", ephemeral=True)
            logger.debug(f"Invalid character sheet URL from user {interaction.user.id}: {error_msg}")
            return

        await db.ensure_user(target_user_id)

        # Check if character already exists
        char_name = char_name.strip()  # Use trimmed version
        existing = await db.get_character(target_user_id, char_name)
        if existing:
            if target_user_id == interaction.user.id:
                await interaction.response.send_message(f"❌ Character '{char_name}' already exists.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Character '{char_name}' already exists for {user.display_name}.", ephemeral=True)
            return

        # Create character
        try:
            await db.create_character(target_user_id, char_name, image_url, sheet_url)
            if target_user_id == interaction.user.id:
                await interaction.response.send_message(f"✅ Character '{char_name}' created and set as active.", ephemeral=True)
            else:
                await interaction.response.send_message(f"✅ Character '{char_name}' created for {user.display_name}.", ephemeral=True)
        except DuplicateCharacterError:
            await interaction.response.send_message(f"❌ Character '{char_name}' already exists.", ephemeral=True)
        except DatabaseError as e:
            logger.error(f"Database error creating character '{char_name}' for user {target_user_id}: {e}")
            await interaction.response.send_message(
                "⚠️ Database temporarily unavailable. Please try again in a moment.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Unexpected error creating character '{char_name}' for user {target_user_id}: {e}")
            await interaction.response.send_message(
                "❌ An unexpected error occurred. Please try again later.",
                ephemeral=True
            )

    @bot.tree.command(name="xp_delete")
    @app_commands.describe(name="Character name to delete")
    @app_commands.autocomplete(name=character_autocomplete)
    @app_commands.checks.cooldown(2, 60.0, key=lambda i: i.user.id)
    async def xp_delete(interaction: discord.Interaction, name: str):
        user_id = interaction.user.id
        await db.ensure_user(user_id)

        deleted = await db.delete_character(user_id, name)
        if not deleted:
            await interaction.response.send_message("❌ Character not found.", ephemeral=True)
            return

        await interaction.response.send_message(f"🗑️ Deleted character '{name}'.", ephemeral=True)

    @bot.tree.command(name="xp_active", description="Set one of your characters as active")
    @app_commands.describe(char_name="Name of the character to activate")
    @app_commands.autocomplete(char_name=character_autocomplete)
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

    @bot.tree.command(name="xp_edit", description="Edit character details (name, image, sheet)")
    @app_commands.describe(
        char_name="Name of the character to edit",
        new_name="New name for the character (optional)",
        image_url="New image URL (optional, use 'remove' to clear)",
        sheet_url="New character sheet URL (optional, use 'remove' to clear)"
    )
    @app_commands.autocomplete(char_name=character_autocomplete)
    @app_commands.checks.cooldown(3, 60.0, key=lambda i: i.user.id)
    async def xp_edit(interaction: discord.Interaction, char_name: str,
                     new_name: str = None, image_url: str = None, sheet_url: str = None):
        user_id = interaction.user.id
        await db.ensure_user(user_id)

        # Check if at least one field is being updated
        if not any([new_name, image_url, sheet_url]):
            await interaction.response.send_message(
                "❌ Please specify at least one field to update (new_name, image_url, or sheet_url).",
                ephemeral=True
            )
            return

        # Find the character (with fuzzy matching)
        chars = await db.list_characters(user_id)
        char_names = [c['name'] for c in chars]
        matched_name = char_name

        if char_name not in char_names:
            # Try fuzzy match
            matches = difflib.get_close_matches(char_name, char_names, n=1, cutoff=0.6)
            if not matches:
                await interaction.response.send_message(f"❌ Character '{char_name}' not found.", ephemeral=True)
                return
            matched_name = matches[0]

        # Validate new name if provided
        if new_name:
            is_valid, error_msg = validate_character_name(new_name)
            if not is_valid:
                await interaction.response.send_message(f"❌ New name: {error_msg}", ephemeral=True)
                return
            new_name = new_name.strip()

        # Handle image_url
        processed_image_url = None
        if image_url:
            if image_url.lower() == 'remove':
                processed_image_url = ''  # Empty string to remove
            else:
                is_valid, error_msg = validate_image_url(image_url)
                if not is_valid:
                    await interaction.response.send_message(f"❌ Image URL: {error_msg}", ephemeral=True)
                    return
                processed_image_url = image_url

        # Handle sheet_url
        processed_sheet_url = None
        if sheet_url:
            if sheet_url.lower() == 'remove':
                processed_sheet_url = ''  # Empty string to remove
            else:
                is_valid, error_msg = validate_character_sheet_url(sheet_url)
                if not is_valid:
                    await interaction.response.send_message(f"❌ Character sheet URL: {error_msg}", ephemeral=True)
                    return
                processed_sheet_url = sheet_url

        # Update character
        try:
            success = await db.update_character(
                user_id,
                matched_name,
                new_name=new_name,
                image_url=processed_image_url,
                character_sheet_url=processed_sheet_url
            )

            if success:
                updated_fields = []
                if new_name:
                    updated_fields.append(f"name → '{new_name}'")
                if processed_image_url is not None:
                    updated_fields.append("image" + (" removed" if processed_image_url == '' else " updated"))
                if processed_sheet_url is not None:
                    updated_fields.append("character sheet" + (" removed" if processed_sheet_url == '' else " updated"))

                display_name = new_name if new_name else matched_name
                await interaction.response.send_message(
                    f"✅ Updated '{display_name}': {', '.join(updated_fields)}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Character '{matched_name}' not found.",
                    ephemeral=True
                )
        except DuplicateCharacterError:
            await interaction.response.send_message(
                f"❌ A character named '{new_name}' already exists.",
                ephemeral=True
            )
        except DatabaseError as e:
            logger.error(f"Database error updating character '{matched_name}' for user {user_id}: {e}")
            await interaction.response.send_message(
                "⚠️ Database temporarily unavailable. Please try again in a moment.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Unexpected error updating character '{matched_name}' for user {user_id}: {e}")
            await interaction.response.send_message(
                "❌ An unexpected error occurred. Please try again later.",
                ephemeral=True
            )

    @bot.tree.command(name="xp_request", description="Request XP for a character")
    @app_commands.describe(
        char_name="Character to request XP for",
        amount="Amount of XP requested",
        memo="Reason for XP request"
    )
    @app_commands.autocomplete(char_name=character_autocomplete)
    @app_commands.checks.cooldown(5, 300.0, key=lambda i: i.user.id)
    async def xp_request(interaction: discord.Interaction, char_name: str, amount: int, memo: str):
        user_id = interaction.user.id
        await db.ensure_user(user_id)

        # Check if user has any characters
        characters = await db.list_characters(user_id)
        if not characters:
            await interaction.response.send_message("❌ You don't have any characters yet.", ephemeral=True)
            return

        # Find the character
        char = await db.get_character(user_id, char_name)
        if not char:
            # Try fuzzy match
            char_names = [c['name'] for c in characters]
            matches = difflib.get_close_matches(char_name, char_names, n=1, cutoff=0.6)
            if not matches:
                await interaction.response.send_message(f"❌ Character '{char_name}' not found.", ephemeral=True)
                return
            char = await db.get_character(user_id, matches[0])

        # Validate amount
        if amount <= 0:
            await interaction.response.send_message("❌ XP amount must be positive.", ephemeral=True)
            return

        if amount > 25000:
            await interaction.response.send_message("❌ XP requests are limited to 25000 XP per request.", ephemeral=True)
            return

        # Check if request channel is configured
        request_channel_id = await db.get_xp_request_channel(guild_id)
        if not request_channel_id:
            await interaction.response.send_message(
                "❌ XP request channel is not configured. Contact an administrator.",
                ephemeral=True
            )
            return

        # Get the request channel
        request_channel = bot.get_channel(request_channel_id)
        if not request_channel:
            await interaction.response.send_message(
                "❌ XP request channel not found. Contact an administrator.",
                ephemeral=True
            )
            return

        # Get current level and XP info
        from utils.xp import get_level_and_progress
        xp_amount = char['xp']
        level, progress, required = get_level_and_progress(xp_amount)

        # Create the request embed
        embed = discord.Embed(
            title=f"XP Request - {char['name']}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        # Player ID field
        embed.add_field(
            name="**Player**",
            value=f"<@{user_id}>",
            inline=False
        )

        # Current Level and Total XP (inline)
        embed.add_field(
            name="**Current Level**",
            value=str(level),
            inline=True
        )

        embed.add_field(
            name="**Current Total XP**",
            value=f"{xp_amount:,}",
            inline=True
        )

        # Requested amount
        embed.add_field(
            name="**Requested Amount**",
            value=f"{amount:,} XP",
            inline=False
        )

        # Reason
        embed.add_field(
            name="**Reason**",
            value=memo,
            inline=False
        )

        # Add character image as thumbnail
        from ui.character_view import DEFAULT_CHARACTER_IMAGE
        image_url = char.get("image_url") or DEFAULT_CHARACTER_IMAGE
        embed.set_thumbnail(url=image_url)

        embed.set_footer(text=f"Request by {interaction.user.display_name}")

        # Create the approval view
        view = XPRequestView(user_id, char['id'], char['name'], user_id, amount, memo, db)

        # Post to request channel
        try:
            await request_channel.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ XP request submitted for **{char['name']}** ({amount} XP).\nAdministrators will review your request.",
                ephemeral=True
            )
            logger.info(f"XP request submitted by user {user_id} for character '{char['name']}': {amount} XP")
        except Exception as e:
            logger.error(f"Failed to post XP request: {e}")
            await interaction.response.send_message(
                "❌ Failed to submit XP request. Contact an administrator.",
                ephemeral=True
            )

