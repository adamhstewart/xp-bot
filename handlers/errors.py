"""
Error handlers for XP Bot
"""
import logging
from discord.ext import commands
from discord import app_commands
from utils.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    CharacterError,
    XPBotError
)

logger = logging.getLogger('xp-bot')


def setup_error_handlers(bot):
    """Register error handlers with the bot"""

    @bot.tree.error
    async def on_app_command_error(interaction, error: app_commands.AppCommandError):
        """Handle errors from slash commands"""
        # Unwrap the actual error if it's wrapped in CommandInvokeError
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

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

        elif isinstance(error, DatabaseConnectionError):
            # Database connection issues
            logger.error(f"Database connection error in /{interaction.command.name}: {error}")
            await interaction.response.send_message(
                "⚠️ Unable to connect to database. Please try again in a few moments.",
                ephemeral=True
            )

        elif isinstance(error, DatabaseError):
            # General database errors
            logger.error(f"Database error in /{interaction.command.name}: {error}")
            await interaction.response.send_message(
                "⚠️ Database temporarily unavailable. Please try again in a moment.",
                ephemeral=True
            )

        elif isinstance(error, CharacterError):
            # Character-specific errors (already handled in commands, but catch here too)
            logger.warning(f"Character error in /{interaction.command.name}: {error}")
            await interaction.response.send_message(
                f"❌ {str(error)}",
                ephemeral=True
            )

        elif isinstance(error, XPBotError):
            # Other custom errors
            logger.error(f"XP Bot error in /{interaction.command.name}: {error}")
            await interaction.response.send_message(
                f"❌ {str(error)}",
                ephemeral=True
            )

        else:
            # Unexpected errors - log and show generic message
            logger.error(f"Unexpected error in /{interaction.command.name}: {error}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ An unexpected error occurred. Please try again later.",
                    ephemeral=True
                )
            except:
                # Response already sent, try followup
                try:
                    await interaction.followup.send(
                        "❌ An unexpected error occurred.",
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
