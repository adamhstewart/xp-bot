#!/usr/bin/env python3
"""
XP Bot - Discord bot for tracking RP and HF XP
Main entry point that initializes bot and registers all commands/handlers
"""
import os
import logging
import discord
from discord.ext import commands
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

# Environment configuration
GUILD_ID = int(os.getenv("GUILD_ID", 0))
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    logger.error("DISCORD_BOT_TOKEN environment variable not set")
    exit(1)

# Initialize database
db = Database()

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Import and register all components
from handlers.events import setup_events
from handlers.errors import setup_error_handlers
from commands.character import setup_character_commands
from commands.admin import setup_admin_commands
from commands.info import setup_info_commands

# Setup handlers and commands
setup_events(bot, db, GUILD_ID)
setup_error_handlers(bot)
setup_character_commands(bot, db)
setup_admin_commands(bot, db, GUILD_ID)
setup_info_commands(bot, db, GUILD_ID)

logger.info("All commands and handlers registered")

# Run the bot
if __name__ == "__main__":
    logger.info("Starting XP Bot...")
    bot.run(TOKEN)
