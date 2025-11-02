#!/usr/bin/env python3
"""
One-time script to clear guild-specific commands from production bot
Run this with production bot credentials to remove duplicate commands
"""
import os
import asyncio
import discord
from discord.ext import commands

# Get production bot token from Fly secrets
TOKEN = input("Enter PRODUCTION bot token: ")
GUILD_ID = int(input("Enter Guild ID (1378809553583603804): "))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

    # Clear guild-specific commands
    guild = discord.Object(id=GUILD_ID)
    bot.tree.clear_commands(guild=guild)
    await bot.tree.sync(guild=guild)

    print(f"✅ Cleared all guild-specific commands from guild {GUILD_ID}")
    print("The production bot should now only show global commands (no duplicates)")

    await bot.close()

if __name__ == "__main__":
    print("This script will clear guild-specific commands from your production bot")
    print("Global commands will remain unchanged")
    bot.run(TOKEN)
