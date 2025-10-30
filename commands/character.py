"""
Character management commands for XP Bot
"""
import logging
import difflib
import discord
from discord import app_commands
from utils.xp import get_level_and_progress
from utils.validation import validate_character_name, validate_image_url
from utils.exceptions import (
    DatabaseError,
    CharacterNotFoundError,
    DuplicateCharacterError
)

logger = logging.getLogger('xp-bot')


def setup_character_commands(bot, db):
    """Register character management commands"""

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

    @bot.tree.command(name="xp", description="View XP, level, and progress for a character")
    @app_commands.describe(char_name="Optional character name (defaults to active)")
    @app_commands.autocomplete(char_name=character_autocomplete)
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
        except DuplicateCharacterError:
            await interaction.response.send_message(f"❌ Character '{char_name}' already exists.", ephemeral=True)
        except DatabaseError as e:
            logger.error(f"Database error creating character '{char_name}' for user {user_id}: {e}")
            await interaction.response.send_message(
                "⚠️ Database temporarily unavailable. Please try again in a moment.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Unexpected error creating character '{char_name}' for user {user_id}: {e}")
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
