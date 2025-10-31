"""
XP Request approval view for XP Bot
"""
import discord
import logging

logger = logging.getLogger('xp-bot')


class XPRequestView(discord.ui.View):
    """View with buttons to approve or deny XP requests"""

    def __init__(self, requester_id: int, character_id: int, character_name: str, user_id: int, amount: int, memo: str, db):
        super().__init__(timeout=None)  # No timeout for request views
        self.requester_id = requester_id  # Who made the request
        self.character_id = character_id
        self.character_name = character_name
        self.user_id = user_id  # Character owner
        self.amount = amount
        self.memo = memo
        self.db = db

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="approve_xp")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Approve the XP request"""
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can approve XP requests.", ephemeral=True)
            return

        # Grant the XP
        await self.db.award_xp(self.user_id, self.character_name, self.amount)

        # Log the XP grant
        await self.db.log_xp_grant(self.character_id, interaction.user.id, self.amount, f"Approved request: {self.memo}")

        # Get updated character info
        from utils.xp import get_level_and_progress
        updated_char = await self.db.get_character(self.user_id, self.character_name)
        new_xp = updated_char['xp']
        new_level, progress, required = get_level_and_progress(new_xp)

        # Update the embed to show approval and new stats
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()

        # Update the Current Total XP field (it's the 3rd field, index 2)
        embed.set_field_at(2, name="**New Total XP**", value=f"{new_xp:,}", inline=True)

        # Add progress bar
        if progress is not None:
            percentage = int((progress / required) * 100)
            bar = int((progress / required) * 20)
            progress_text = f"`[{'█'*bar}{'-'*(20-bar)}]` {progress}/{required} ({percentage}%)"
            embed.add_field(
                name="**New Level Progress**",
                value=progress_text,
                inline=False
            )

        # Add approval status
        embed.add_field(
            name="**Status**",
            value=f"✅ Approved by {interaction.user.mention}",
            inline=False
        )

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        # Post a notification to the channel about the approval
        from ui.character_view import DEFAULT_CHARACTER_IMAGE
        notification_embed = discord.Embed(
            title=f"XP Granted - {self.character_name}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )

        notification_embed.add_field(
            name="**Player**",
            value=f"<@{self.user_id}>",
            inline=False
        )

        notification_embed.add_field(
            name="**New Level**",
            value=str(new_level),
            inline=True
        )

        notification_embed.add_field(
            name="**New Total XP**",
            value=f"{new_xp:,}",
            inline=True
        )

        notification_embed.add_field(
            name="**Amount Granted**",
            value=f"{self.amount:,} XP",
            inline=False
        )

        if progress is not None:
            percentage = int((progress / required) * 100)
            bar = int((progress / required) * 20)
            progress_text = f"`[{'█'*bar}{'-'*(20-bar)}]` {progress}/{required} ({percentage}%)"
            notification_embed.add_field(
                name="**Current Level Progress**",
                value=progress_text,
                inline=False
            )

        notification_embed.add_field(
            name="**Reason**",
            value=f"Request approved: {self.memo}",
            inline=False
        )

        # Add character image
        image_url = updated_char.get("image_url") or DEFAULT_CHARACTER_IMAGE
        notification_embed.set_thumbnail(url=image_url)

        notification_embed.set_footer(text=f"Approved by {interaction.user.display_name}")

        try:
            await interaction.channel.send(embed=notification_embed)
        except Exception as e:
            logger.error(f"Failed to post approval notification: {e}")

        # Notify the requester
        try:
            requester = await interaction.client.fetch_user(self.requester_id)
            await requester.send(
                f"✅ Your XP request for **{self.character_name}** has been approved!\n"
                f"Amount: {self.amount:,} XP\n"
                f"New Total XP: {new_xp:,}\n"
                f"New Level: {new_level}\n"
                f"Approved by: {interaction.user.display_name}"
            )
        except:
            logger.warning(f"Could not send approval notification to user {self.requester_id}")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="deny_xp")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deny the XP request"""
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can deny XP requests.", ephemeral=True)
            return

        # Update the embed to show denial
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="Status", value=f"❌ Denied by {interaction.user.mention}", inline=False)

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        # Notify the requester
        try:
            requester = await interaction.client.fetch_user(self.requester_id)
            await requester.send(
                f"❌ Your XP request for **{self.character_name}** has been denied.\n"
                f"Amount: {self.amount} XP\n"
                f"Denied by: {interaction.user.display_name}"
            )
        except:
            logger.warning(f"Could not send denial notification to user {self.requester_id}")
