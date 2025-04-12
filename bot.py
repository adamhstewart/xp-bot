import os
import json
import difflib
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
XP_FILE = "xp.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Load and save XP data
def load_xp():
    try:
        with open(XP_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_xp(data):
    with open(XP_FILE, "w") as f:
        json.dump(data, f, indent=4)

xp_data = load_xp()

# Ensure user has an XP structure
def ensure_user(user_id):
    if user_id not in xp_data:
        xp_data[user_id] = {"active": None, "characters": {}}

# Event: award XP to active character
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    ensure_user(user_id)

    active = xp_data[user_id]["active"]
    if active and active in xp_data[user_id]["characters"]:
        xp_data[user_id]["characters"][active]["xp"] += 1
        save_xp(xp_data)

    await bot.process_commands(message)

# Command: create a new character
@bot.command()
async def create_character(ctx, name: str, image_url: str):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    if name in xp_data[user_id]["characters"]:
        await ctx.send(f"A character named **{name}** already exists.")
        return

    xp_data[user_id]["characters"][name] = {
        "xp": 0,
        "image_url": image_url
    }

    if not xp_data[user_id]["active"]:
        xp_data[user_id]["active"] = name

    save_xp(xp_data)
    await ctx.send(f"Character **{name}** created and set as active!")

# Command: set the active character
@bot.command()
async def set_active(ctx, *, name: str):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    characters = xp_data[user_id]["characters"]

    # Try exact match
    if name in characters:
        char_name = name
    else:
        # Fuzzy match
        close_matches = difflib.get_close_matches(name, characters.keys(), n=1, cutoff=0.6)
        if not close_matches:
            await ctx.send(f"No character found matching **{name}**.")
            return
        char_name = close_matches[0]

    xp_data[user_id]["active"] = char_name
    save_xp(xp_data)
    await ctx.send(f"**{char_name}** is now your active character!")

# Command: show active character and XP
@bot.command()
async def my_character(ctx, *, name: str = None):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    characters = xp_data[user_id]["characters"]

    # If no name given, use active
    if not name:
        name = xp_data[user_id]["active"]

    if not name:
        await ctx.send("You don't have any active or named character. Use `!create_character`.")
        return

    # Try exact match
    if name in characters:
        char_name = name
    else:
        # Fuzzy match
        close_matches = difflib.get_close_matches(name, characters.keys(), n=1, cutoff=0.6)
        if not close_matches:
            await ctx.send(f"No character found matching **{name}**.")
            return
        char_name = close_matches[0]

    char = characters[char_name]
    embed = discord.Embed(title=char_name, description=f"XP: {char['xp']}")
    embed.set_image(url=char["image_url"])
    await ctx.send(embed=embed)

# Command: check XP for a character (defaults to active)
@bot.command()
async def xp(ctx, name: str = None):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    if name is None:
        name = xp_data[user_id]["active"]

    if not name or name not in xp_data[user_id]["characters"]:
        await ctx.send("Character not found or no active character set.")
        return

    char = xp_data[user_id]["characters"][name]
    await ctx.send(f"**{name}** has **{char['xp']} XP**.")

# Command: delete a character
@bot.command()
async def delete_character(ctx, name: str):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    if name not in xp_data[user_id]["characters"]:
        await ctx.send(f"No character named **{name}** found.")
        return

    del xp_data[user_id]["characters"][name]

    # Reset active character if deleted
    if xp_data[user_id]["active"] == name:
        remaining = list(xp_data[user_id]["characters"].keys())
        xp_data[user_id]["active"] = remaining[0] if remaining else None

    save_xp(xp_data)
    await ctx.send(f"Character **{name}** has been deleted.")

@bot.command()
async def list_characters(ctx):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    characters = xp_data[user_id]["characters"]
    active = xp_data[user_id]["active"]

    if not characters:
        await ctx.send("You don't have any characters yet. Use `!create_character` to start.")
        return

    lines = []
    for name, data in characters.items():
        prefix = "🟢 " if name == active else "⚪"
        lines.append(f"{prefix} **{name}** — {data['xp']} XP")

    message = "\n".join(lines)
    await ctx.send(f"**Your Characters:**\n{message}")

bot.run(TOKEN)
