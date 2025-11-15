"""
Quest confirmation and interaction views
"""
import logging
import discord
from datetime import date

logger = logging.getLogger('xp-bot')


class QuestEndConfirmView(discord.ui.View):
    """Confirmation view for ending a quest"""

    def __init__(self, quest_id: int, quest_name: str, end_date: date, db, guild_id: int):
        super().__init__(timeout=180)  # 3 minute timeout
        self.quest_id = quest_id
        self.quest_name = quest_name
        self.end_date = end_date
        self.db = db
        self.guild_id = guild_id
        self.value = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel quest completion"""
        await interaction.response.edit_message(
            content=f"Quest ending cancelled. **{self.quest_name}** remains active.",
            view=None
        )
        self.stop()

    @discord.ui.button(label="Confirm End Quest", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm quest completion"""
        try:
            # Complete the quest
            success = await self.db.complete_quest(self.quest_id, self.end_date)
            if not success:
                await interaction.response.send_message(
                    f"Quest '{self.quest_name}' could not be completed (may already be completed).",
                    ephemeral=True
                )
                self.stop()
                return

            # Get quest details for summary
            quest = await self.db.get_quest(self.quest_id)
            participants = await self.db.get_quest_participants(self.quest_id)
            dms = await self.db.get_quest_dms(self.quest_id)
            monsters = await self.db.get_quest_monsters(self.quest_id)

            # Build summary message
            from utils.quest_xp import calculate_quest_xp

            summary = f"✅ Quest **{self.quest_name}** completed!\n"
            summary += f"Start: {quest['start_date']} | End: {self.end_date}\n"
            summary += f"Type: {quest['quest_type']}\n\n"

            if participants:
                summary += f"**Participants ({len(participants)}):**\n"
                for p in participants:
                    summary += f"- {p['character_name']} (Level {p['starting_level']})\n"
                summary += "\n"

            if dms:
                summary += f"**DMs:**\n"
                for dm in dms:
                    dm_tag = "Primary" if dm['is_primary'] else "Co-DM"
                    summary += f"- <@{dm['user_id']}> ({dm_tag})\n"
                summary += "\n"

            # XP Calculation if monsters exist
            if monsters:
                quest_xp_data = calculate_quest_xp(monsters)
                summary += f"**Monsters Defeated ({len(monsters)}):**\n"
                for m in quest_xp_data['breakdown']:
                    if 'error' in m:
                        name_part = f"{m['monster_name']} - " if m['monster_name'] else ""
                        summary += f"- ❌ {m['count']}x {name_part}CR {m['cr']}\n"
                    else:
                        name_part = f"{m['monster_name']} - " if m['monster_name'] else ""
                        summary += f"- {m['count']}x {name_part}CR {m['cr']} ({m['xp_per_monster']:,} XP ea)\n"

                summary += f"\n**Total XP:** {quest_xp_data['total_xp']:,}\n"
                if participants:
                    xp_per_pc = quest_xp_data['total_xp'] // len(participants)
                    summary += f"**XP per PC:** {xp_per_pc:,}\n"
            else:
                summary += f"⚠️ No monsters were added to this quest.\n"

            summary += f"\n_Quest is now locked. No more changes can be made._"

            # Update the original message
            await interaction.response.edit_message(content=summary, view=None)
            logger.info(f"Quest '{self.quest_name}' (ID: {self.quest_id}) completed by user {interaction.user.id}")

        except Exception as e:
            logger.error(f"Error completing quest '{self.quest_name}': {e}")
            await interaction.response.send_message(
                "An error occurred while completing the quest.",
                ephemeral=True
            )
        finally:
            self.stop()

    async def on_timeout(self):
        """Called when the view times out"""
        # Disable all buttons
        for item in self.children:
            item.disabled = True


class QuestDeleteConfirmView(discord.ui.View):
    """Confirmation view for deleting a quest"""

    def __init__(self, quest_id: int, quest_name: str, db, participant_count: int, monster_count: int):
        super().__init__(timeout=180)  # 3 minute timeout
        self.quest_id = quest_id
        self.quest_name = quest_name
        self.db = db
        self.participant_count = participant_count
        self.monster_count = monster_count

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel quest deletion"""
        await interaction.response.edit_message(
            content=f"Deletion cancelled. **{self.quest_name}** has not been deleted.",
            view=None
        )
        self.stop()

    @discord.ui.button(label="Delete Quest", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm quest deletion"""
        try:
            # Delete the quest
            deleted = await self.db.delete_quest(self.quest_id)
            if not deleted:
                await interaction.response.send_message(
                    f"Quest '{self.quest_name}' could not be deleted (may already be completed or deleted).",
                    ephemeral=True
                )
                self.stop()
                return

            # Build success message
            message = f"✅ Quest **{self.quest_name}** has been deleted.\n\n"
            message += f"Removed:\n"
            message += f"- {self.participant_count} participant(s)\n"
            message += f"- {self.monster_count} monster(s)\n"
            message += f"\n_All quest data has been permanently removed._"

            # Update the original message
            await interaction.response.edit_message(content=message, view=None)
            logger.info(f"Quest '{self.quest_name}' (ID: {self.quest_id}) deleted by user {interaction.user.id}")

        except Exception as e:
            logger.error(f"Error deleting quest '{self.quest_name}': {e}")
            await interaction.response.send_message(
                "An error occurred while deleting the quest.",
                ephemeral=True
            )
        finally:
            self.stop()

    async def on_timeout(self):
        """Called when the view times out"""
        # Disable all buttons
        for item in self.children:
            item.disabled = True
