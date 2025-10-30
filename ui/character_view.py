"""
Character navigation view for XP Bot
"""
import discord
from utils.xp import get_level_and_progress

# Default character image if none provided
DEFAULT_CHARACTER_IMAGE = "https://placehold.co/400x400/5865F2/FFFFFF/png?text=No+Image"


class CharacterNavigationView(discord.ui.View):
    """View with buttons to navigate between characters and set active"""

    def __init__(self, target_user_id: int, viewer_user_id: int, characters: list, active_char_name: str, db, current_index: int = 0):
        super().__init__(timeout=180)  # 3 minute timeout
        self.target_user_id = target_user_id  # Owner of the characters
        self.viewer_user_id = viewer_user_id  # Person viewing the characters
        self.characters = characters
        self.active_char_name = active_char_name
        self.db = db
        self.current_index = current_index
        self.is_owner = (target_user_id == viewer_user_id)

        # Update button states
        self._update_buttons()

    def _update_buttons(self):
        """Update button states based on current position"""
        # Disable prev button if at start
        self.prev_button.disabled = (self.current_index == 0)

        # Disable next button if at end
        self.next_button.disabled = (self.current_index >= len(self.characters) - 1)

        # Hide set active button if not the owner, otherwise disable if already active
        if self.is_owner:
            current_char = self.characters[self.current_index]
            self.set_active_button.disabled = (current_char['name'] == self.active_char_name)
        else:
            # Hide the button by removing it from the view
            if hasattr(self, 'set_active_button'):
                self.remove_item(self.set_active_button)

    def _create_embed(self) -> discord.Embed:
        """Create embed for current character"""
        char = self.characters[self.current_index]
        xp_amount = char["xp"]
        level, progress, required = get_level_and_progress(xp_amount)

        # Add green dot to title if active character (only when viewing own characters)
        title = char['name']
        if self.is_owner and char['name'] == self.active_char_name:
            title += " 🟢"

        # Create embed with character sheet URL if available
        sheet_url = char.get('character_sheet_url')
        embed = discord.Embed(
            title=title,
            url=sheet_url if sheet_url else None,
            color=discord.Color.blue()
        )

        # Add Player ID field
        embed.add_field(
            name="Player ID",
            value=f"<@{char['user_id']}>",
            inline=False
        )

        # Add Level and Total XP fields (inline with each other)
        embed.add_field(
            name="Level",
            value=str(level),
            inline=True
        )

        embed.add_field(
            name="Total XP",
            value=f"{xp_amount:,}",
            inline=True
        )

        # Add Current Level Progress field
        if progress is not None:
            percentage = int((progress / required) * 100)
            bar = int((progress / required) * 20)
            progress_text = f"`[{'█'*bar}{'-'*(20-bar)}]` {progress}/{required} ({percentage}%)"
            embed.add_field(
                name="Current Level Progress",
                value=progress_text,
                inline=False
            )

        # Add character image as thumbnail (smaller, right-aligned)
        image_url = char.get("image_url") or DEFAULT_CHARACTER_IMAGE
        embed.set_thumbnail(url=image_url)

        # Add footer showing position
        embed.set_footer(text=f"Character {self.current_index + 1} of {len(self.characters)}")

        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous character"""
        if interaction.user.id != self.viewer_user_id:
            await interaction.response.send_message("❌ This is not your view.", ephemeral=True)
            return

        self.current_index = max(0, self.current_index - 1)
        self._update_buttons()

        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next character"""
        if interaction.user.id != self.viewer_user_id:
            await interaction.response.send_message("❌ This is not your view.", ephemeral=True)
            return

        self.current_index = min(len(self.characters) - 1, self.current_index + 1)
        self._update_buttons()

        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Set Active", style=discord.ButtonStyle.primary, custom_id="set_active")
    async def set_active_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set current character as active (only visible to owner)"""
        if interaction.user.id != self.viewer_user_id or not self.is_owner:
            await interaction.response.send_message("❌ You cannot set active characters for other users.", ephemeral=True)
            return

        char = self.characters[self.current_index]
        char_name = char['name']

        # Set as active
        await self.db.set_active_character(self.target_user_id, char_name)
        self.active_char_name = char_name

        # Update buttons and embed
        self._update_buttons()
        embed = self._create_embed()

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"🟢 '{char_name}' is now your active character.", ephemeral=True)

    async def on_timeout(self):
        """Called when view times out"""
        # Disable all buttons on timeout
        for item in self.children:
            item.disabled = True
