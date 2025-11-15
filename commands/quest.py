"""
Quest tracking commands for XP Bot
Allows DMs to track quests with PC participants, DMs, and monsters/CR for XP calculation
"""
import logging
import discord
from discord import app_commands
from datetime import date, datetime
from typing import Optional, List
from utils.xp import get_level_and_progress
from utils.quest_xp import calculate_quest_xp
from ui.quest_view import QuestEndConfirmView, QuestDeleteConfirmView

logger = logging.getLogger('xp-bot')


def is_level_in_bracket(level: int, bracket: str) -> bool:
    """Check if a character level is within a level bracket"""
    try:
        # Parse bracket string (e.g., "3-4", "5-7", "17-20")
        min_level, max_level = map(int, bracket.split('-'))
        return min_level <= level <= max_level
    except (ValueError, AttributeError):
        return False


def setup_quest_commands(bot, db, guild_id):
    """Register quest management commands"""

    async def has_dm_permission(interaction: discord.Interaction) -> bool:
        """Check if user has DM permissions (admin or character creation role)"""
        # Admins always have permission
        if interaction.user.guild_permissions.administrator:
            return True

        # Check if user has any of the DM roles (using character creation roles)
        allowed_role_ids = await db.get_character_creation_roles(guild_id)

        # If no roles configured, allow everyone
        if not allowed_role_ids:
            return True

        # Check if user has any allowed role
        user_role_ids = [role.id for role in interaction.user.roles]
        return any(role_id in allowed_role_ids for role_id in user_role_ids)

    async def active_quest_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for active quest names"""
        try:
            quest_names = await db.search_active_quests(guild_id, current or "", limit=25)
            return [
                app_commands.Choice(name=name, value=name)
                for name in quest_names
            ]
        except Exception as e:
            logger.error(f"Error in quest autocomplete: {e}")
            return []

    async def completed_quest_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for completed quest names"""
        try:
            quest_names = await db.search_completed_quests(guild_id, current or "", limit=25)
            return [
                app_commands.Choice(name=name, value=name)
                for name in quest_names
            ]
        except Exception as e:
            logger.error(f"Error in completed quest autocomplete: {e}")
            return []

    async def all_characters_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for all character names (for quest PC selection)"""
        try:
            # Check if user has DM permission
            if not await has_dm_permission(interaction):
                return []

            # Search all characters across all users
            char_names = await db.search_all_character_names(current, limit=25)
            return [
                app_commands.Choice(name=name, value=name)
                for name in char_names
            ]
        except Exception as e:
            logger.error(f"Error in all characters autocomplete: {e}")
            return []

    async def user_characters_autocomplete(interaction: discord.Interaction, current: str):
        """Autocomplete for user's own character names"""
        try:
            user_id = interaction.user.id
            await db.ensure_user(user_id)
            characters = await db.list_characters(user_id)

            # Filter by current input
            filtered = [c for c in characters if current.lower() in c['name'].lower()]
            return [
                app_commands.Choice(name=c['name'], value=c['name'])
                for c in filtered[:25]
            ]
        except Exception as e:
            logger.error(f"Error in user characters autocomplete: {e}")
            return []

    @bot.tree.command(name="quest_start", description="[DM] Start a new quest")
    @app_commands.describe(
        quest_name="Name of the quest",
        quest_type="Type of quest",
        level_bracket="Level bracket for the quest",
        start_date="Start date (YYYY-MM-DD format, defaults to today)",
        primary_dm="Primary DM for the quest (defaults to you)"
    )
    @app_commands.choices(quest_type=[
        app_commands.Choice(name="Campaign", value="Campaign"),
        app_commands.Choice(name="Mission", value="Mission"),
        app_commands.Choice(name="Colosseum", value="Colosseum"),
        app_commands.Choice(name="Battle", value="Battle")
    ])
    @app_commands.choices(level_bracket=[
        app_commands.Choice(name="3-4", value="3-4"),
        app_commands.Choice(name="5-7", value="5-7"),
        app_commands.Choice(name="8-10", value="8-10"),
        app_commands.Choice(name="11-13", value="11-13"),
        app_commands.Choice(name="14-16", value="14-16"),
        app_commands.Choice(name="17-20", value="17-20")
    ])
    async def quest_start(
        interaction: discord.Interaction,
        quest_name: str,
        quest_type: str,
        level_bracket: str,
        start_date: Optional[str] = None,
        primary_dm: Optional[discord.User] = None
    ):
        """Start a new quest and add participants"""
        # Check DM permission
        if not await has_dm_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to create quests. Contact an administrator.",
                ephemeral=True
            )
            return

        # Validate quest name
        if not quest_name or len(quest_name.strip()) == 0:
            await interaction.response.send_message("Quest name is required.", ephemeral=True)
            return

        if len(quest_name) > 200:
            await interaction.response.send_message("Quest name must be 200 characters or less.", ephemeral=True)
            return

        # Validate quest type
        if not quest_type or len(quest_type.strip()) == 0:
            await interaction.response.send_message("Quest type is required.", ephemeral=True)
            return

        if len(quest_type) > 100:
            await interaction.response.send_message("Quest type must be 100 characters or less.", ephemeral=True)
            return

        # Parse start date
        quest_start_date = date.today()
        if start_date:
            try:
                quest_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                await interaction.response.send_message(
                    "Invalid date format. Please use YYYY-MM-DD (e.g., 2025-01-15).",
                    ephemeral=True
                )
                return

        # Check if quest with same name already exists (active)
        existing = await db.get_quest_by_name(guild_id, quest_name.strip())
        if existing:
            await interaction.response.send_message(
                f"An active quest named '{quest_name}' already exists.",
                ephemeral=True
            )
            return

        # Determine primary DM (default to current user)
        dm_user = primary_dm if primary_dm else interaction.user

        # Show modal or message to continue
        dm_mention = dm_user.mention if dm_user.id != interaction.user.id else "You"
        await interaction.response.send_message(
            f"Setting up quest **{quest_name}** ({quest_type})\n"
            f"Level Bracket: {level_bracket}\n"
            f"Start date: {quest_start_date}\n"
            f"Primary DM: {dm_mention}\n\n"
            f"Use `/quest_add_pc` to add player characters to this quest.\n"
            f"Use `/quest_add_dm` to add additional DMs.",
            ephemeral=True
        )

        # Create the quest
        try:
            quest_id = await db.create_quest(
                guild_id,
                quest_name.strip(),
                quest_type.strip(),
                level_bracket,
                quest_start_date,
                dm_user.id
            )
            logger.info(f"Quest '{quest_name}' (ID: {quest_id}) created by user {interaction.user.id}, primary DM: {dm_user.id}")

        except Exception as e:
            logger.error(f"Error creating quest '{quest_name}': {e}")
            await interaction.followup.send(
                "An error occurred while creating the quest. Please try again.",
                ephemeral=True
            )

    @bot.tree.command(name="quest_add_pc", description="[DM] Add a PC to an active quest")
    @app_commands.describe(
        quest_name="Name of the quest",
        character="Character name (type to search)"
    )
    @app_commands.autocomplete(quest_name=active_quest_autocomplete, character=all_characters_autocomplete)
    async def quest_add_pc(
        interaction: discord.Interaction,
        quest_name: str,
        character: str
    ):
        """Add a PC to an active quest"""
        # Check DM permission
        if not await has_dm_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to modify quests.",
                ephemeral=True
            )
            return

        # Find the quest
        quest = await db.get_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Quest '{quest_name}' not found or not active.",
                ephemeral=True
            )
            return

        # Find the character (search across all users)
        char_result = await db.find_character_by_name_any_user(character)
        if not char_result:
            await interaction.response.send_message(
                f"Character '{character}' not found.",
                ephemeral=True
            )
            return

        user_id, char_data = char_result
        character_id = char_data['id']
        character_name = char_data['name']
        current_xp = char_data['xp']

        # Calculate starting level
        starting_level, _, _ = get_level_and_progress(current_xp)

        # Add participant
        try:
            await db.add_quest_participant(quest['id'], character_id, starting_level, current_xp)
            await interaction.response.send_message(
                f"Added **{character_name}** to quest **{quest_name}**\n"
                f"Starting Level: {starting_level} (XP: {current_xp:,})",
                ephemeral=True
            )
            logger.info(f"Added character {character_name} (ID: {character_id}) to quest {quest['id']}")
        except Exception as e:
            logger.error(f"Error adding character to quest: {e}")
            await interaction.response.send_message(
                "An error occurred while adding the character. They may already be in this quest.",
                ephemeral=True
            )

    @bot.tree.command(name="quest_remove_pc", description="[DM] Remove a PC from an active quest")
    @app_commands.describe(
        quest_name="Name of the quest",
        character="Character name to remove (type to search)"
    )
    @app_commands.autocomplete(quest_name=active_quest_autocomplete, character=all_characters_autocomplete)
    async def quest_remove_pc(
        interaction: discord.Interaction,
        quest_name: str,
        character: str
    ):
        """Remove a PC from an active quest"""
        # Check DM permission
        if not await has_dm_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to modify quests.",
                ephemeral=True
            )
            return

        # Find the quest
        quest = await db.get_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Active quest '{quest_name}' not found.",
                ephemeral=True
            )
            return

        # Check if quest is completed
        if quest['status'] == 'completed':
            await interaction.response.send_message(
                f"Cannot remove participants from completed quest **{quest_name}**.",
                ephemeral=True
            )
            return

        # Find the character (search across all users)
        char_result = await db.find_character_by_name_any_user(character)
        if not char_result:
            await interaction.response.send_message(
                f"Character '{character}' not found.",
                ephemeral=True
            )
            return

        user_id, char_data = char_result
        character_id = char_data['id']
        character_name = char_data['name']

        # Remove participant
        try:
            removed = await db.remove_quest_participant(quest['id'], character_id)
            if removed:
                await interaction.response.send_message(
                    f"Removed **{character_name}** from quest **{quest_name}**",
                    ephemeral=True
                )
                logger.info(f"Removed character {character_name} (ID: {character_id}) from quest {quest['id']}")
            else:
                await interaction.response.send_message(
                    f"**{character_name}** is not in quest **{quest_name}**.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error removing character from quest: {e}")
            await interaction.response.send_message(
                "An error occurred while removing the character.",
                ephemeral=True
            )

    @bot.tree.command(name="quest_join", description="Join an active quest with your character")
    @app_commands.describe(
        quest_name="Name of the quest to join",
        character="Your character to join with (type to search)"
    )
    @app_commands.autocomplete(quest_name=active_quest_autocomplete, character=user_characters_autocomplete)
    async def quest_join(
        interaction: discord.Interaction,
        quest_name: str,
        character: str
    ):
        """Allow players to join quests with their chosen character"""
        # Find the character by name (only for this user)
        char_result = await db.get_character(interaction.user.id, character)
        if not char_result:
            await interaction.response.send_message(
                f"You don't have a character named '{character}'.",
                ephemeral=True
            )
            return

        character_id = char_result['id']
        character_name = char_result['name']
        current_xp = char_result['xp']
        current_level, _, _ = get_level_and_progress(current_xp)

        # Find the quest (active only)
        quest = await db.get_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Active quest '{quest_name}' not found.",
                ephemeral=True
            )
            return

        # Validate level bracket
        if not is_level_in_bracket(current_level, quest['level_bracket']):
            await interaction.response.send_message(
                f"Your character **{character_name}** (Level {current_level}) cannot join this quest.\n"
                f"This quest is for level bracket **{quest['level_bracket']}**.",
                ephemeral=True
            )
            return

        # Add participant
        try:
            await db.add_quest_participant(quest['id'], character_id, current_level, current_xp)
            await interaction.response.send_message(
                f"**{character_name}** (Level {current_level}) has joined quest **{quest_name}**!\n"
                f"Starting Level: {current_level} (XP: {current_xp:,})",
                ephemeral=True
            )
            logger.info(f"Player {interaction.user.id} joined quest {quest['id']} with character {character_name} (ID: {character_id})")
        except Exception as e:
            logger.error(f"Error adding player to quest: {e}")
            await interaction.response.send_message(
                "An error occurred while joining the quest. You may already be in this quest.",
                ephemeral=True
            )

    @bot.tree.command(name="quest_add_dm", description="[DM] Add an additional DM to an active quest")
    @app_commands.describe(
        quest_name="Name of the quest",
        dm_user="User to add as DM"
    )
    @app_commands.autocomplete(quest_name=active_quest_autocomplete)
    async def quest_add_dm(
        interaction: discord.Interaction,
        quest_name: str,
        dm_user: discord.User
    ):
        """Add an additional DM to an active quest"""
        # Check DM permission
        if not await has_dm_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to modify quests.",
                ephemeral=True
            )
            return

        # Find the quest
        quest = await db.get_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Quest '{quest_name}' not found or not active.",
                ephemeral=True
            )
            return

        # Add DM
        try:
            await db.add_quest_dm(quest['id'], dm_user.id, is_primary=False)
            await interaction.response.send_message(
                f"Added **{dm_user.display_name}** as DM to quest **{quest_name}**",
                ephemeral=True
            )
            logger.info(f"Added DM {dm_user.id} to quest {quest['id']}")
        except Exception as e:
            logger.error(f"Error adding DM to quest: {e}")
            await interaction.response.send_message(
                "An error occurred while adding the DM. They may already be a DM for this quest.",
                ephemeral=True
            )

    @bot.tree.command(name="quest_end", description="[DM] Complete an active quest")
    @app_commands.describe(
        quest_name="Name of the quest to complete",
        end_date="End date (YYYY-MM-DD format, defaults to today)"
    )
    @app_commands.autocomplete(quest_name=active_quest_autocomplete)
    async def quest_end(
        interaction: discord.Interaction,
        quest_name: str,
        end_date: Optional[str] = None
    ):
        """Complete a quest and prepare to add monsters/CR"""
        # Check DM permission
        if not await has_dm_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to modify quests.",
                ephemeral=True
            )
            return

        # Find the quest
        quest = await db.get_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Quest '{quest_name}' not found or not active.",
                ephemeral=True
            )
            return

        # Parse end date
        quest_end_date = date.today()
        if end_date:
            try:
                quest_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                await interaction.response.send_message(
                    "Invalid date format. Please use YYYY-MM-DD (e.g., 2025-01-15).",
                    ephemeral=True
                )
                return

        # Validate end date is not before start date
        if quest_end_date < quest['start_date']:
            await interaction.response.send_message(
                f"End date ({quest_end_date}) cannot be before start date ({quest['start_date']}).",
                ephemeral=True
            )
            return

        # Get preview of quest details
        participants = await db.get_quest_participants(quest['id'])
        monsters = await db.get_quest_monsters(quest['id'])

        # Build confirmation message
        confirm_msg = f"⚠️ **Confirm Quest Completion**\n\n"
        confirm_msg += f"Quest: **{quest_name}**\n"
        confirm_msg += f"End Date: {quest_end_date}\n"
        confirm_msg += f"Participants: {len(participants)}\n"
        confirm_msg += f"Monsters Added: {len(monsters)}\n\n"

        if not monsters:
            confirm_msg += f"⚠️ **Warning:** No monsters have been added yet. You can still end the quest, but there will be no XP calculation.\n\n"

        confirm_msg += f"**Once completed, this quest will be locked and no further changes can be made.**\n"
        confirm_msg += f"Are you sure you want to end this quest?"

        # Create confirmation view
        view = QuestEndConfirmView(quest['id'], quest_name, quest_end_date, db, guild_id)

        try:
            await interaction.response.send_message(confirm_msg, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error showing quest end confirmation: {e}")
            await interaction.response.send_message(
                "An error occurred while preparing quest completion.",
                ephemeral=True
            )

    @bot.tree.command(name="quest_delete", description="[DM] Delete an active quest")
    @app_commands.describe(quest_name="Name of the quest to delete")
    @app_commands.autocomplete(quest_name=active_quest_autocomplete)
    async def quest_delete(
        interaction: discord.Interaction,
        quest_name: str
    ):
        """Delete an active quest (cannot delete completed quests)"""
        # Check DM permission
        if not await has_dm_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to delete quests.",
                ephemeral=True
            )
            return

        # Find the quest
        quest = await db.get_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Active quest '{quest_name}' not found.",
                ephemeral=True
            )
            return

        # Check if quest is completed
        if quest['status'] == 'completed':
            await interaction.response.send_message(
                f"Cannot delete completed quest **{quest_name}**.\n"
                f"Completed quests are locked to preserve history.",
                ephemeral=True
            )
            return

        # Get quest details for confirmation
        participants = await db.get_quest_participants(quest['id'])
        monsters = await db.get_quest_monsters(quest['id'])

        # Build confirmation message
        confirm_msg = f"⚠️ **Confirm Quest Deletion**\n\n"
        confirm_msg += f"Quest: **{quest_name}**\n"
        confirm_msg += f"Type: {quest['quest_type']}\n"
        confirm_msg += f"Level Bracket: {quest['level_bracket']}\n"
        confirm_msg += f"Participants: {len(participants)}\n"
        confirm_msg += f"Monsters Added: {len(monsters)}\n\n"
        confirm_msg += f"**This will permanently delete:**\n"
        confirm_msg += f"- The quest and all its data\n"
        confirm_msg += f"- All participant records\n"
        confirm_msg += f"- All monster/encounter records\n"
        confirm_msg += f"- All DM assignments\n\n"
        confirm_msg += f"**This action cannot be undone!**\n"
        confirm_msg += f"Are you sure you want to delete this quest?"

        # Create confirmation view
        view = QuestDeleteConfirmView(
            quest['id'],
            quest_name,
            db,
            len(participants),
            len(monsters)
        )

        try:
            await interaction.response.send_message(confirm_msg, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error showing quest delete confirmation: {e}")
            await interaction.response.send_message(
                "An error occurred while preparing quest deletion.",
                ephemeral=True
            )

    @bot.tree.command(name="quest_add_monster", description="[DM] Add monster/encounter to a quest")
    @app_commands.describe(
        quest_name="Name of the quest",
        cr="Challenge Rating (e.g., '1', '1/2', '1/4', '5')",
        count="Number of this monster (defaults to 1)",
        monster_name="Optional: Monster name for reference"
    )
    @app_commands.autocomplete(quest_name=active_quest_autocomplete)
    async def quest_add_monster(
        interaction: discord.Interaction,
        quest_name: str,
        cr: str,
        count: Optional[int] = 1,
        monster_name: Optional[str] = None
    ):
        """Add a monster/encounter to a quest for XP calculation"""
        # Check DM permission
        if not await has_dm_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to modify quests.",
                ephemeral=True
            )
            return

        # Find the quest (only active quests)
        quest = await db.get_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Quest '{quest_name}' not found or not active.",
                ephemeral=True
            )
            return

        # Check if quest is completed
        if quest['status'] == 'completed':
            await interaction.response.send_message(
                f"❌ Quest **{quest_name}** is already completed and locked.\n"
                f"Monsters cannot be added to completed quests.",
                ephemeral=True
            )
            return

        # Validate CR
        cr = cr.strip()
        valid_crs = [
            "0", "1/8", "1/4", "1/2",
            "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
            "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
            "21", "22", "23", "24", "25", "26", "27", "28", "29", "30"
        ]
        if cr not in valid_crs:
            await interaction.response.send_message(
                f"Invalid CR '{cr}'. Valid CRs: 0, 1/8, 1/4, 1/2, 1-30.",
                ephemeral=True
            )
            return

        # Validate count
        if count < 1:
            await interaction.response.send_message(
                "Count must be at least 1.",
                ephemeral=True
            )
            return

        # Add monster
        try:
            await db.add_quest_monster(quest['id'], cr, monster_name, count)

            display_name = f"{monster_name} " if monster_name else ""
            await interaction.response.send_message(
                f"Added {count}x {display_name}(CR {cr}) to quest **{quest_name}**",
                ephemeral=True
            )
            logger.info(f"Added monster (CR {cr}, count {count}) to quest {quest['id']}")

        except Exception as e:
            logger.error(f"Error adding monster to quest: {e}")
            await interaction.response.send_message(
                "An error occurred while adding the monster.",
                ephemeral=True
            )

    @bot.tree.command(name="quest_info", description="View details of an active quest")
    @app_commands.describe(quest_name="Name of the quest")
    @app_commands.autocomplete(quest_name=active_quest_autocomplete)
    async def quest_info(interaction: discord.Interaction, quest_name: str):
        """Display detailed information about an active quest"""
        # Find the quest (active only)
        quest = await db.get_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Active quest '{quest_name}' not found.",
                ephemeral=True
            )
            return

        # Get quest details
        participants = await db.get_quest_participants(quest['id'])
        dms = await db.get_quest_dms(quest['id'])
        monsters = await db.get_quest_monsters(quest['id'])

        # Build embed
        embed = discord.Embed(
            title=f"{quest['name']}",
            description=f"**Type:** {quest['quest_type']}\n**Level Bracket:** {quest['level_bracket']}\n**Status:** {quest['status'].capitalize()}",
            color=discord.Color.blue() if quest['status'] == 'active' else discord.Color.green()
        )

        # Dates
        date_info = f"**Start:** {quest['start_date']}"
        if quest['end_date']:
            date_info += f"\n**End:** {quest['end_date']}"
        embed.add_field(name="Timeline", value=date_info, inline=False)

        # DMs
        if dms:
            dm_list = []
            for dm in dms:
                dm_tag = " (Primary)" if dm['is_primary'] else ""
                dm_list.append(f"<@{dm['user_id']}>{dm_tag}")
            embed.add_field(name=f"DMs ({len(dms)})", value="\n".join(dm_list), inline=True)

        # Participants
        if participants:
            pc_list = []
            for p in participants:
                pc_list.append(f"{p['character_name']} (Lvl {p['starting_level']})")
            embed.add_field(name=f"Participants ({len(participants)})", value="\n".join(pc_list), inline=True)
        else:
            embed.add_field(name="Participants", value="*No participants yet*", inline=True)

        # Monsters and XP Calculation
        if monsters:
            # Calculate XP
            quest_xp_data = calculate_quest_xp(monsters)

            monster_list = []
            for m in quest_xp_data['breakdown']:
                if 'error' in m:
                    name_part = f"{m['monster_name']} - " if m['monster_name'] else ""
                    monster_list.append(f"❌ {m['count']}x {name_part}CR {m['cr']}")
                else:
                    name_part = f"{m['monster_name']} - " if m['monster_name'] else ""
                    monster_list.append(f"{m['count']}x {name_part}CR {m['cr']} ({m['xp_per_monster']:,} XP ea)")

            embed.add_field(
                name=f"Monsters ({len(monsters)})",
                value="\n".join(monster_list),
                inline=False
            )

            # XP Summary
            if participants:
                xp_per_pc = quest_xp_data['total_xp'] // len(participants)
                xp_summary = f"**Total XP:** {quest_xp_data['total_xp']:,}\n"
                xp_summary += f"**Per PC:** {xp_per_pc:,} XP"
            else:
                xp_summary = f"**Total XP:** {quest_xp_data['total_xp']:,}"

            embed.add_field(name="XP Calculation", value=xp_summary, inline=False)

        embed.set_footer(text=f"Quest ID: {quest['id']}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="quest_list", description="List all active quests")
    async def quest_list(interaction: discord.Interaction):
        """List all active quests in the server"""
        quests = await db.get_active_quests(guild_id)

        if not quests:
            await interaction.response.send_message(
                "No active quests.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Active Quests",
            color=discord.Color.blue()
        )

        for quest in quests[:25]:  # Limit to 25 for embed field limits
            # Get participant count
            participants = await db.get_quest_participants(quest['id'])
            pc_count = len(participants)

            value = f"**Type:** {quest['quest_type']}\n"
            value += f"**Level Bracket:** {quest['level_bracket']}\n"
            value += f"**Started:** {quest['start_date']}\n"
            value += f"**Participants:** {pc_count}"

            embed.add_field(
                name=quest['name'],
                value=value,
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="quest_list_completed", description="List all completed quests")
    async def quest_list_completed(interaction: discord.Interaction):
        """List all completed quests in the server"""
        quests = await db.get_completed_quests(guild_id)

        if not quests:
            await interaction.response.send_message(
                "No completed quests.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Completed Quests",
            color=discord.Color.green()
        )

        for quest in quests[:25]:  # Limit to 25 for embed field limits
            # Get participant count
            participants = await db.get_quest_participants(quest['id'])
            pc_count = len(participants)

            value = f"**Type:** {quest['quest_type']}\n"
            value += f"**Level Bracket:** {quest['level_bracket']}\n"
            value += f"**Started:** {quest['start_date']}\n"
            value += f"**Ended:** {quest['end_date']}\n"
            value += f"**Participants:** {pc_count}"

            embed.add_field(
                name=quest['name'],
                value=value,
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="quest_info_completed", description="View details of a completed quest")
    @app_commands.describe(quest_name="Name of the completed quest")
    @app_commands.autocomplete(quest_name=completed_quest_autocomplete)
    async def quest_info_completed(interaction: discord.Interaction, quest_name: str):
        """Display detailed information about a completed quest"""
        # Find the quest (completed only)
        quest = await db.get_completed_quest_by_name(guild_id, quest_name)
        if not quest:
            await interaction.response.send_message(
                f"Completed quest '{quest_name}' not found.",
                ephemeral=True
            )
            return

        # Get quest details
        participants = await db.get_quest_participants(quest['id'])
        dms = await db.get_quest_dms(quest['id'])
        monsters = await db.get_quest_monsters(quest['id'])

        # Build embed
        embed = discord.Embed(
            title=f"📜 {quest['name']}",
            description=f"**Type:** {quest['quest_type']}\n**Level Bracket:** {quest['level_bracket']}\n**Status:** Completed",
            color=discord.Color.green()
        )

        # Dates
        date_info = f"**Start:** {quest['start_date']}\n**End:** {quest['end_date']}"
        embed.add_field(name="Timeline", value=date_info, inline=False)

        # DMs
        if dms:
            dm_list = []
            for dm in dms:
                dm_tag = " (Primary)" if dm['is_primary'] else ""
                dm_list.append(f"<@{dm['user_id']}>{dm_tag}")
            embed.add_field(name=f"DMs ({len(dms)})", value="\n".join(dm_list), inline=True)

        # Participants
        if participants:
            pc_list = []
            for p in participants:
                pc_list.append(f"{p['character_name']} (Lvl {p['starting_level']})")
            embed.add_field(name=f"Participants ({len(participants)})", value="\n".join(pc_list), inline=True)

        # Monsters and XP Calculation
        if monsters:
            # Calculate XP
            quest_xp_data = calculate_quest_xp(monsters)

            monster_list = []
            for m in quest_xp_data['breakdown']:
                if 'error' in m:
                    name_part = f"{m['monster_name']} - " if m['monster_name'] else ""
                    monster_list.append(f"❌ {m['count']}x {name_part}CR {m['cr']}")
                else:
                    name_part = f"{m['monster_name']} - " if m['monster_name'] else ""
                    monster_list.append(f"{m['count']}x {name_part}CR {m['cr']} ({m['xp_per_monster']:,} XP ea)")

            embed.add_field(
                name=f"Monsters ({len(monsters)})",
                value="\n".join(monster_list),
                inline=False
            )

            # XP Summary
            if participants:
                xp_per_pc = quest_xp_data['total_xp'] // len(participants)
                xp_summary = f"**Total XP:** {quest_xp_data['total_xp']:,}\n"
                xp_summary += f"**Per PC:** {xp_per_pc:,} XP"
            else:
                xp_summary = f"**Total XP:** {quest_xp_data['total_xp']:,}"

            embed.add_field(name="XP Calculation", value=xp_summary, inline=False)

        embed.set_footer(text=f"Quest ID: {quest['id']} • Completed")

        await interaction.response.send_message(embed=embed, ephemeral=True)
