"""
Event handlers for XP Bot - handles on_ready and on_message
"""
import os
import logging
import discord
from utils.xp import should_reset_xp, perform_daily_reset

logger = logging.getLogger('xp-bot')


def setup_events(bot, db, guild_id):
    """Register event handlers with the bot"""

    @bot.event
    async def on_ready():
        logger.info(f"Bot '{bot.user.name}' is online")

        # Connect to database
        await db.connect()
        await db.initialize_schema()

        env = os.getenv("ENV", "prod")
        guild_id_env = os.getenv("GUILD_ID")

        if env == "dev" and guild_id_env:
            logger.info("Environment: development")
            guild = discord.Object(id=int(guild_id_env))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} slash commands to dev guild {guild_id_env}")
        else:
            logger.info("Environment: production")

            # Clear any old guild-specific commands from production bot
            if guild_id_env:
                guild = discord.Object(id=int(guild_id_env))
                bot.tree.clear_commands(guild=guild)
                await bot.tree.sync(guild=guild)
                logger.info(f"Cleared guild-specific commands from guild {guild_id_env}")

            # Sync global commands
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} global slash commands")

        logger.info("Available slash commands:")
        for cmd in bot.tree.get_commands():
            logger.info(f"  /{cmd.name}")

    @bot.event
    async def on_message(message):
        """Check each message to see if it should be awarded RP or HF XP"""
        config = await db.get_config(guild_id)

        # HF tracking (bot messages with embeds)
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

        # RP tracking (user messages)
        elif not message.author.bot and message.channel.id in config.get("rp_channels", []):
            user_id = message.author.id
            await db.ensure_user(user_id)

            # Check if we need to reset daily caps
            if await should_reset_xp(db, user_id):
                await perform_daily_reset(db, user_id)

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
