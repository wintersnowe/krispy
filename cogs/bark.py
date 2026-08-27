import discord
from discord.ext import commands
from discord import app_commands
import random
import aiosqlite
import re

# ---------- Button View ----------
class BarkView(discord.ui.View):
    def __init__(self, original_text: str):
        super().__init__()
        self.original_text = original_text

    @discord.ui.button(label="Show Original", style=discord.ButtonStyle.primary)
    async def show_original(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = self.original_text
        if len(text) > 1900:
            text = text[:1900] + "... (truncated)"
        await interaction.response.send_message(f"**Original message:**\n{text}", ephemeral=True)


# ---------- Cog ----------
class BarkCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "Krispy.db"
        self.webhook_cache = {}

    async def cog_load(self):
        await self.init_db()

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bark_users (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    show_original INTEGER NOT NULL DEFAULT 1,   -- 1 = show button, 0 = hide
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            await db.commit()

    # ---------- Database Helpers ----------
    async def is_enabled(self, user_id: int, guild_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT enabled FROM bark_users WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None and bool(row[0])

    async def get_show_original(self, user_id: int, guild_id: int) -> bool:
        """Return True if the user wants to show the button, default True."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT show_original FROM bark_users WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                # If row is None (user not inserted yet), default to True
                return row is None or bool(row[0])

    async def toggle_user(self, user_id: int, guild_id: int, show_original: bool = True) -> bool:
        """
        Toggle the user's enabled state. Also updates show_original if the user exists.
        Returns the NEW enabled state (True = enabled, False = disabled).
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT enabled, show_original FROM bark_users WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()

            if row is None:
                # New user – insert with enabled=1 and given show_original
                new_enabled = 1
                await db.execute(
                    'INSERT INTO bark_users (user_id, guild_id, enabled, show_original) VALUES (?, ?, ?, ?)',
                    (user_id, guild_id, new_enabled, 1 if show_original else 0)
                )
            else:
                # Toggle enabled
                new_enabled = 1 - row[0]
                # Also update show_original (even if it's the same, it's fine)
                await db.execute(
                    'UPDATE bark_users SET enabled = ?, show_original = ? WHERE user_id = ? AND guild_id = ?',
                    (new_enabled, 1 if show_original else 0, user_id, guild_id)
                )

            await db.commit()
            return bool(new_enabled)

    # ---------- Bark Generator (ONLY barks) ----------
    def generate_bark_only(self, text: str) -> str:
        """Converts any text into a sequence of random bark sounds only."""
        if not text:
            return "*silent puppy stare*"

        bark_sounds = ["woof", "bark", "arf", "grrr", "ruff", "yip", "bow-wow", "awoo"]
        words = text.split()
        if not words:
            return "*silent puppy stare*"

        # One bark per word in the original message
        barks = [random.choice(bark_sounds) for _ in words]
        return " ".join(barks)

    # ---------- Webhook Manager ----------
    async def get_or_create_webhook(self, channel: discord.TextChannel):
        if channel.id in self.webhook_cache:
            try:
                await self.webhook_cache[channel.id].fetch()
                return self.webhook_cache[channel.id]
            except discord.NotFound:
                del self.webhook_cache[channel.id]

        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.name == "BarkEchoBot" and webhook.user == self.bot.user:
                self.webhook_cache[channel.id] = webhook
                return webhook

        webhook = await channel.create_webhook(name="BarkEchoBot")
        self.webhook_cache[channel.id] = webhook
        return webhook

    # ---------- Event Listener ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 1. Ignore bots, DMs, webhooks, and media-only messages
        if message.author.bot:
            return
        if message.guild is None:
            return
        if message.webhook_id is not None:
            return

        # Ignore messages with no text or just a link
        content = message.content.strip()
        if not content:
            return
        link_pattern = re.compile(r'^https?://\S+$')
        if link_pattern.match(content):
            return

        # 2. Check if the user is toggled for bark mode
        if not await self.is_enabled(message.author.id, message.guild.id):
            return

        # 3. Get user's preference for showing the button
        show_original = await self.get_show_original(message.author.id, message.guild.id)

        # 4. Transform and send
        original_text = content
        bark_text = self.generate_bark_only(original_text)

        webhook = await self.get_or_create_webhook(message.channel)

        # Delete original
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Attach button only if the user wants it
        view = BarkView(original_text) if show_original else None

        await webhook.send(
            content=bark_text,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            allowed_mentions=discord.AllowedMentions.none(),
            view=view   # None = no button
        )

    # ---------- Slash Command ----------
    @app_commands.command(name="bark", description="Toggle bark mode on a user's messages")
    @app_commands.describe(
        user="The user to enable/disable bark mode for",
        show_original="Show a 'Show Original' button on barked messages? (default True)"
    )
    @app_commands.guild_only()
    async def bark(self, interaction: discord.Interaction, user: discord.Member, show_original: bool = True):
        if user.bot:
            await interaction.response.send_message("🐶 You can't toggle barking on a bot!", ephemeral=True)
            return
        if user.id == self.bot.user.id:
            await interaction.response.send_message("🐶 I can't bark at myself!", ephemeral=True)
            return

        # Toggle the user and store their show_original preference
        new_state = await self.toggle_user(user.id, interaction.guild_id, show_original)
        status = "enabled" if new_state else "disabled"
        emoji = "🐕" if new_state else "🔇"

        # Show what the preference was set to
        button_status = "with" if show_original else "without"

        await interaction.response.send_message(
            f"{emoji} Bark mode **{status}** for {user.mention} ({button_status} the 'Show Original' button).",
            ephemeral=True
        )

# ---------- Cog Setup ----------
async def setup(bot):
    await bot.add_cog(BarkCog(bot))