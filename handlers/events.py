"""
Event handlers for XP Bot - handles on_ready and on_message
"""
import os
import logging
import discord
from utils.xp import should_reset_xp, perform_daily_reset, get_level_and_progress

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
        """Check each message to see if it should be awarded RP or Survival XP"""
        config = await db.get_config(guild_id)

        # Survival tracking (bot messages with embeds) - hunting, fishing, foraging
        if message.author.bot and message.embeds and message.channel.id in config.get("hf_channels", []):
            embed = message.embeds[0]
            title = embed.title.lower() if embed.title else ""
            description = embed.description.lower() if embed.description else ""
            field_texts = " ".join(f"{field.name.lower()} {field.value.lower()}" for field in embed.fields)
            combined_text = f"{title} {description} {field_texts}"

            logger.debug(f"Survival Embed detected in #{getattr(message.channel, 'name', 'DM')} by {getattr(message.author, 'display_name', str(message.author))}")
            logger.debug(f"Embed title: {title}")
            logger.debug(f"Embed description: {description}")

            is_hunting = "goes hunting" in combined_text
            is_fishing = "goes fishing" in combined_text
            is_foraging = "goes foraging" in combined_text
            is_success = "time to harvest" in combined_text or "time to gut and harvest" in combined_text

            logger.debug(f"Hunting: {is_hunting}, Fishing: {is_fishing}, Foraging: {is_foraging}, Success: {is_success}")

            if is_hunting or is_fishing or is_foraging:
                char_name = embed.title.split(" goes ")[0].strip()
                logger.debug(f"Trying to match character name: '{char_name}'")

                # Find all characters with this name
                matches = await db.find_all_characters_by_name(char_name)

                if not matches:
                    logger.warning(f"No matching character found for Survival activity: '{char_name}'")
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

                # Check daily Survival cap
                if char_data['daily_hf'] >= config.get('daily_hf_cap', 5):
                    logger.debug(f"Character '{char_name_actual}' has reached daily Survival cap")
                    return

                # Calculate XP award
                base_xp = config.get('hf_attempt_xp', 1)
                bonus = config.get('hf_success_xp', 5) if is_success else 0
                xp_award = min(base_xp + bonus, config['daily_hf_cap'] - char_data['daily_hf'])

                # Award XP
                xp_result = await db.award_xp(user_id, char_name_actual, xp_award, daily_hf_delta=xp_award)

                logger.info(f"Awarded {xp_award} Survival XP to '{char_name_actual}' (user {user_id})")

                # Check for level-up and send notifications
                if xp_result['leveled_up']:
                    old_level = xp_result['old_level']
                    new_level = xp_result['new_level']
                    new_xp = xp_result['new_xp']

                    # Get updated character info
                    updated_char = await db.get_character(user_id, char_name_actual)

                    # Send level-up notification to log channel
                    log_channel_id = await db.get_log_channel()
                    if log_channel_id:
                        log_channel = bot.get_channel(log_channel_id)
                        if log_channel:
                            from ui.character_view import DEFAULT_CHARACTER_IMAGE
                            level_embed = discord.Embed(
                                title=f"🎉 Level Up! - {char_name_actual}",
                                description=f"**{char_name_actual}** has leveled up from **Level {old_level}** to **Level {new_level}**!",
                                color=discord.Color.gold(),
                                timestamp=discord.utils.utcnow()
                            )

                            level_embed.add_field(
                                name="**Player**",
                                value=f"<@{user_id}>",
                                inline=True
                            )

                            level_embed.add_field(
                                name="**Old Level**",
                                value=str(old_level),
                                inline=True
                            )

                            level_embed.add_field(
                                name="**New Level**",
                                value=str(new_level),
                                inline=True
                            )

                            level_embed.add_field(
                                name="**Source**",
                                value="Survival Activity (Hunting/Fishing/Foraging)",
                                inline=False
                            )

                            # Add character sheet link if available
                            if updated_char.get('character_sheet_url'):
                                level_embed.add_field(
                                    name="**Character Sheet**",
                                    value=f"[View Sheet]({updated_char['character_sheet_url']})",
                                    inline=False
                                )

                            level_embed.add_field(
                                name="**Action Required**",
                                value="Please update your character sheet to reflect your new level!",
                                inline=False
                            )

                            # Add character image
                            image_url = updated_char.get("image_url") or DEFAULT_CHARACTER_IMAGE
                            level_embed.set_thumbnail(url=image_url)

                            try:
                                await log_channel.send(embed=level_embed)
                                logger.info(f"Posted level-up notification for {char_name_actual} to log channel")
                            except Exception as e:
                                logger.error(f"Failed to post Survival level-up notification: {e}")

                    # Send DM to character owner
                    try:
                        owner = await bot.fetch_user(user_id)

                        # Create rich embed for level-up DM
                        from ui.character_view import DEFAULT_CHARACTER_IMAGE
                        levelup_dm_embed = discord.Embed(
                            title=f"🎉 Level Up! - {char_name_actual}",
                            description=f"**{char_name_actual}** has leveled up from **Level {old_level}** to **Level {new_level}**!",
                            color=discord.Color.gold(),
                            timestamp=discord.utils.utcnow()
                        )

                        levelup_dm_embed.add_field(
                            name="**Player**",
                            value=f"<@{user_id}>",
                            inline=False
                        )

                        levelup_dm_embed.add_field(
                            name="**Old Level**",
                            value=str(old_level),
                            inline=True
                        )

                        levelup_dm_embed.add_field(
                            name="**New Level**",
                            value=str(new_level),
                            inline=True
                        )

                        levelup_dm_embed.add_field(
                            name="**New Total XP**",
                            value=f"{new_xp:,}",
                            inline=False
                        )

                        levelup_dm_embed.add_field(
                            name="**Source**",
                            value="Survival Activity (Hunting/Fishing/Foraging)",
                            inline=False
                        )

                        if updated_char.get('character_sheet_url'):
                            levelup_dm_embed.add_field(
                                name="**Action Required**",
                                value=f"Please update your [character sheet]({updated_char['character_sheet_url']}) to reflect your new level!",
                                inline=False
                            )
                        else:
                            levelup_dm_embed.add_field(
                                name="**Action Required**",
                                value="Please update your character sheet to reflect your new level!",
                                inline=False
                            )

                        # Add character image
                        image_url = updated_char.get("image_url") or DEFAULT_CHARACTER_IMAGE
                        levelup_dm_embed.set_thumbnail(url=image_url)

                        await owner.send(embed=levelup_dm_embed)
                        logger.info(f"Sent level-up DM to user {user_id}")
                    except Exception as e:
                        logger.warning(f"Could not send Survival level-up DM to user {user_id}: {e}")

        # Prized Species XP Request tracking (bot messages with prized rewards)
        survival_channels = config.get("survival_channels", [])
        if message.author.bot and message.embeds and (not survival_channels or message.channel.id in survival_channels):
            embed = message.embeds[0]

            # Check for prized species awards
            prized_detected = False
            char_name = None
            xp_amount = 0
            activity_type = None

            # Extract character name from title
            if embed.title:
                title = embed.title
                if " goes fishing" in title:
                    char_name = title.split(" goes fishing")[0].strip()
                    activity_type = "fishing"
                elif " goes hunting" in title:
                    char_name = title.split(" goes hunting")[0].strip()
                    activity_type = "hunting"
                elif " goes foraging" in title:
                    char_name = title.split(" goes foraging")[0].strip()
                    activity_type = "foraging"

            # Check embed fields for prized species awards
            if char_name and activity_type:
                for field in embed.fields:
                    field_name = field.name if field.name else ""
                    field_value = field.value if field.value else ""

                    # Check for prized species indicators
                    if "🏆 PRIZED" in field_name:
                        prized_detected = True

                        # Extract XP amounts from field value
                        # Look for "earned **100gp**" or "**+500gp**"
                        if "earned **100gp**" in field_value:
                            xp_amount += 100
                        if "**+500gp**" in field_value:
                            xp_amount += 500

                        logger.debug(f"Prized species detected: {char_name}, {activity_type}, {xp_amount} XP")

            # If prized species detected, create XP request and add reactions
            if prized_detected and xp_amount > 0:
                try:
                    # Add robot emoji to indicate detection
                    await message.add_reaction("🤖")

                    # Find character across all users
                    matches = await db.find_all_characters_by_name(char_name)

                    if not matches:
                        logger.warning(f"No matching character found for prized species: '{char_name}'")
                        await message.add_reaction("❌")
                        return

                    # Disambiguate if multiple matches
                    if len(matches) == 1:
                        user_id, char_data = matches[0]
                    else:
                        # Try to disambiguate using message mentions
                        mentioned_user_ids = [mention.id for mention in message.mentions]

                        if mentioned_user_ids:
                            matching_mentions = [(uid, cdata) for uid, cdata in matches if uid in mentioned_user_ids]

                            if len(matching_mentions) == 1:
                                user_id, char_data = matching_mentions[0]
                                logger.info(f"Disambiguated prized species '{char_name}' using mention: user {user_id}")
                            else:
                                logger.warning(f"Cannot disambiguate prized species character '{char_name}'. Skipping XP request.")
                                await message.add_reaction("❌")
                                return
                        else:
                            logger.warning(f"Cannot disambiguate prized species character '{char_name}' - no user mentions. Skipping XP request.")
                            await message.add_reaction("❌")
                            return

                    # Get XP request channel
                    request_channel_id = await db.get_xp_request_channel(guild_id)
                    if not request_channel_id:
                        logger.warning(f"XP request channel not configured, cannot create prized species XP request")
                        await message.add_reaction("❌")
                        return

                    request_channel = bot.get_channel(request_channel_id)
                    if not request_channel:
                        logger.warning(f"XP request channel {request_channel_id} not found")
                        await message.add_reaction("❌")
                        return

                    # Create XP request
                    from utils.xp import get_level_and_progress
                    from ui.xp_request_view import XPRequestView
                    from ui.character_view import DEFAULT_CHARACTER_IMAGE

                    char_name_actual = char_data['name']
                    xp_current = char_data['xp']
                    level, progress, required = get_level_and_progress(xp_current)

                    # Create request embed
                    request_embed = discord.Embed(
                        title=f"XP Request - {char_name_actual}",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )

                    request_embed.add_field(
                        name="**Player**",
                        value=f"<@{user_id}>",
                        inline=False
                    )

                    request_embed.add_field(
                        name="**Current Level**",
                        value=str(level),
                        inline=True
                    )

                    request_embed.add_field(
                        name="**Current Total XP**",
                        value=f"{xp_current:,}",
                        inline=True
                    )

                    request_embed.add_field(
                        name="**Requested Amount**",
                        value=f"{xp_amount:,} XP",
                        inline=False
                    )

                    request_embed.add_field(
                        name="**Reason**",
                        value=f"Prized Species ({activity_type.title()}) - Auto-detected from reward message",
                        inline=False
                    )

                    # Add link to original message
                    request_embed.add_field(
                        name="**Source Message**",
                        value=f"[Jump to Message]({message.jump_url})",
                        inline=False
                    )

                    # Add character image
                    image_url = char_data.get("image_url") or DEFAULT_CHARACTER_IMAGE
                    request_embed.set_thumbnail(url=image_url)

                    request_embed.set_footer(text="Auto-generated from prized species reward")

                    # Create approval view (use bot.user.id as requester since it's auto-generated)
                    view = XPRequestView(bot.user.id, char_data['id'], char_name_actual, user_id, xp_amount,
                                        f"Prized Species ({activity_type.title()}) - Auto-detected", db)

                    # Post to request channel
                    await request_channel.send(embed=request_embed, view=view)

                    # Add green check to indicate success
                    await message.add_reaction("✅")

                    logger.info(f"Created prized species XP request for '{char_name_actual}' (user {user_id}): {xp_amount} XP from {activity_type}")

                except Exception as e:
                    logger.error(f"Failed to create prized species XP request: {e}")
                    try:
                        await message.add_reaction("❌")
                    except:
                        pass

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
                xp_result = await db.award_xp(
                    user_id,
                    active_char['name'],
                    gained_xp,
                    daily_xp_delta=gained_xp,
                    char_buffer_delta=new_buffer - active_char['char_buffer']
                )

                # Check for level-up and send notifications
                if xp_result['leveled_up']:
                    old_level = xp_result['old_level']
                    new_level = xp_result['new_level']
                    new_xp = xp_result['new_xp']
                    char_name = active_char['name']

                    # Get updated character info
                    updated_char = await db.get_character(user_id, char_name)

                    # Send level-up notification to log channel
                    log_channel_id = await db.get_log_channel()
                    if log_channel_id:
                        log_channel = bot.get_channel(log_channel_id)
                        if log_channel:
                            from ui.character_view import DEFAULT_CHARACTER_IMAGE
                            level_embed = discord.Embed(
                                title=f"🎉 Level Up! - {char_name}",
                                description=f"**{char_name}** has leveled up from **Level {old_level}** to **Level {new_level}**!",
                                color=discord.Color.gold(),
                                timestamp=discord.utils.utcnow()
                            )

                            level_embed.add_field(
                                name="**Player**",
                                value=f"<@{user_id}>",
                                inline=True
                            )

                            level_embed.add_field(
                                name="**Old Level**",
                                value=str(old_level),
                                inline=True
                            )

                            level_embed.add_field(
                                name="**New Level**",
                                value=str(new_level),
                                inline=True
                            )

                            level_embed.add_field(
                                name="**Source**",
                                value="Roleplay Activity",
                                inline=False
                            )

                            # Add character sheet link if available
                            if updated_char.get('character_sheet_url'):
                                level_embed.add_field(
                                    name="**Character Sheet**",
                                    value=f"[View Sheet]({updated_char['character_sheet_url']})",
                                    inline=False
                                )

                            level_embed.add_field(
                                name="**Action Required**",
                                value="Please update your character sheet to reflect your new level!",
                                inline=False
                            )

                            # Add character image
                            image_url = updated_char.get("image_url") or DEFAULT_CHARACTER_IMAGE
                            level_embed.set_thumbnail(url=image_url)

                            try:
                                await log_channel.send(embed=level_embed)
                                logger.info(f"Posted level-up notification for {char_name} to log channel")
                            except Exception as e:
                                logger.error(f"Failed to post RP level-up notification: {e}")

                    # Send DM to character owner
                    try:
                        owner = await bot.fetch_user(user_id)

                        # Create rich embed for level-up DM
                        from ui.character_view import DEFAULT_CHARACTER_IMAGE
                        levelup_dm_embed = discord.Embed(
                            title=f"🎉 Level Up! - {char_name}",
                            description=f"**{char_name}** has leveled up from **Level {old_level}** to **Level {new_level}**!",
                            color=discord.Color.gold(),
                            timestamp=discord.utils.utcnow()
                        )

                        levelup_dm_embed.add_field(
                            name="**Player**",
                            value=f"<@{user_id}>",
                            inline=False
                        )

                        levelup_dm_embed.add_field(
                            name="**Old Level**",
                            value=str(old_level),
                            inline=True
                        )

                        levelup_dm_embed.add_field(
                            name="**New Level**",
                            value=str(new_level),
                            inline=True
                        )

                        levelup_dm_embed.add_field(
                            name="**New Total XP**",
                            value=f"{new_xp:,}",
                            inline=False
                        )

                        levelup_dm_embed.add_field(
                            name="**Source**",
                            value="Roleplay Activity",
                            inline=False
                        )

                        if updated_char.get('character_sheet_url'):
                            levelup_dm_embed.add_field(
                                name="**Action Required**",
                                value=f"Please update your [character sheet]({updated_char['character_sheet_url']}) to reflect your new level!",
                                inline=False
                            )
                        else:
                            levelup_dm_embed.add_field(
                                name="**Action Required**",
                                value="Please update your character sheet to reflect your new level!",
                                inline=False
                            )

                        # Add character image
                        image_url = updated_char.get("image_url") or DEFAULT_CHARACTER_IMAGE
                        levelup_dm_embed.set_thumbnail(url=image_url)

                        await owner.send(embed=levelup_dm_embed)
                        logger.info(f"Sent level-up DM to user {user_id}")
                    except Exception as e:
                        logger.warning(f"Could not send RP level-up DM to user {user_id}: {e}")

            elif new_buffer != active_char['char_buffer']:
                # Just update buffer
                await db.update_character_buffer(user_id, active_char['name'], new_buffer)

        await bot.process_commands(message)
