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
        xp_result = await self.db.award_xp(self.user_id, self.character_name, self.amount)

        # Log the XP grant
        await self.db.log_xp_grant(self.character_id, interaction.user.id, self.amount, f"Approved request: {self.memo}")

        # Get updated character info
        from utils.xp import get_level_and_progress
        updated_char = await self.db.get_character(self.user_id, self.character_name)
        new_xp = updated_char['xp']
        new_level, progress, required = get_level_and_progress(new_xp)

        # Check if character leveled up
        leveled_up = xp_result['leveled_up']
        old_level = xp_result['old_level']

        # Send level-up notification if character leveled up
        if leveled_up:
            # Get log channel for level-up notification
            log_channel_id = await self.db.get_log_channel()
            if log_channel_id:
                log_channel = interaction.client.get_channel(log_channel_id)
                if log_channel:
                    from ui.character_view import DEFAULT_CHARACTER_IMAGE
                    level_embed = discord.Embed(
                        title=f"🎉 Level Up! - {self.character_name}",
                        description=f"**{self.character_name}** has leveled up from **Level {old_level}** to **Level {new_level}**!",
                        color=discord.Color.gold(),
                        timestamp=discord.utils.utcnow()
                    )

                    level_embed.add_field(
                        name="**Player**",
                        value=f"<@{self.user_id}>",
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

                    level_embed.set_footer(text=f"Request approved by {interaction.user.display_name}")

                    try:
                        await log_channel.send(embed=level_embed)
                    except Exception as e:
                        logger.error(f"Failed to post level-up notification: {e}")

            # Send DM to character owner
            try:
                owner = await interaction.client.fetch_user(self.user_id)

                # Create rich embed for level-up DM
                from ui.character_view import DEFAULT_CHARACTER_IMAGE
                levelup_dm_embed = discord.Embed(
                    title=f"🎉 Level Up! - {self.character_name}",
                    description=f"**{self.character_name}** has leveled up from **Level {old_level}** to **Level {new_level}**!",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )

                levelup_dm_embed.add_field(
                    name="**Player**",
                    value=f"<@{self.user_id}>",
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
                    name="**Reason**",
                    value=f"{self.memo}",
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

                levelup_dm_embed.set_footer(text=f"Approved by {interaction.user.display_name}")

                await owner.send(embed=levelup_dm_embed)
            except Exception as e:
                logger.warning(f"Could not send level-up DM to user {self.user_id}: {e}")

        # Send XP grant notification to character owner (always sent, in addition to level-up if applicable)
        # This applies to both manual requests and auto-generated requests
        try:
            owner = await interaction.client.fetch_user(self.user_id)

            # Create DM embed matching the log channel format
            from ui.character_view import DEFAULT_CHARACTER_IMAGE
            dm_embed = discord.Embed(
                title=f"XP Granted - {self.character_name}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )

            dm_embed.add_field(
                name="**Player**",
                value=f"<@{self.user_id}>",
                inline=False
            )

            dm_embed.add_field(
                name="**Level**",
                value=str(new_level),
                inline=True
            )

            dm_embed.add_field(
                name="**New Total XP**",
                value=f"{new_xp:,}",
                inline=True
            )

            dm_embed.add_field(
                name="**Amount Granted**",
                value=f"{self.amount:,} XP",
                inline=False
            )

            if progress is not None:
                percentage = int((progress / required) * 100)
                bar = int((progress / required) * 20)
                progress_text = f"`[{'█'*bar}{'-'*(20-bar)}]` {progress}/{required} ({percentage}%)"
                dm_embed.add_field(
                    name="**Current Level Progress**",
                    value=progress_text,
                    inline=False
                )

            dm_embed.add_field(
                name="**Reason**",
                value=f"{self.memo}",
                inline=False
            )

            # Add character image
            image_url = updated_char.get("image_url") or DEFAULT_CHARACTER_IMAGE
            dm_embed.set_thumbnail(url=image_url)

            dm_embed.set_footer(text=f"Approved by {interaction.user.display_name}")

            await owner.send(embed=dm_embed)
            logger.info(f"Sent XP grant notification to character owner {self.user_id}")
        except Exception as e:
            logger.warning(f"Could not send XP grant DM to character owner {self.user_id}: {e}")

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
            name="**Level**",
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

        # Notify the requester (only if different from character owner)
        # Character owner already received a notification above
        if self.requester_id != self.user_id:
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
