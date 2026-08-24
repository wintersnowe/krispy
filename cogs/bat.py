import discord
from discord.ext import commands
from discord import app_commands
import random
import sqlite3
import asyncio

class BatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "Krispy.db"  # SQLite database file
        self.webhook_cache = {}       # Cache webhooks per channel ID

    # ---------- Database Initialization ----------
    async def cog_load(self):
        """Runs when the cog is loaded. Sets up the database table."""
        await self.init_db()

    async def init_db(self):
        """Creates the database table if it doesn't exist."""
        async with sqlite3.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bat_users (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            await db.commit()

    # ---------- Database Helpers ----------
    async def is_enabled(self, user_id: int, guild_id: int) -> bool:
        """Checks if a user has bat chittering enabled in a specific guild."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT enabled FROM bat_users WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None and bool(row[0])

    async def toggle_user(self, user_id: int, guild_id: int) -> bool:
        """
        Toggles the user's bat status in the guild.
        Returns the NEW state (True = enabled, False = disabled).
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Check current state
            async with db.execute(
                'SELECT enabled FROM bat_users WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()

            if row is None:
                # User doesn't exist in DB -> Enable them
                new_state = 1
                await db.execute(
                    'INSERT INTO bat_users (user_id, guild_id, enabled) VALUES (?, ?, ?)',
                    (user_id, guild_id, new_state)
                )
            else:
                # Flip the state (1 -> 0, 0 -> 1)
                new_state = 1 - row[0]
                await db.execute(
                    'UPDATE bat_users SET enabled = ? WHERE user_id = ? AND guild_id = ?',
                    (new_state, user_id, guild_id)
                )

            await db.commit()
            return bool(new_state)

    # ---------- Bat Chitter Generator ----------
    def add_bat_chitters(self, text: str) -> str:
        """Inserts bat-like sounds randomly throughout the message."""
        if not text:
            return "*inaudible bat screeching*"

        chitters = [
            " *chitter*", " *squeak*", " *eek*",
            " *flap flap*", " *screech*", " *chirp*",
            " *rustle*", " *click*", " *skree*"
        ]

        words = text.split()
        if not words:
            return text

        new_words = []
        counter = 0

        for word in words:
            new_words.append(word)
            counter += 1

            if counter >= random.randint(3, 6):
                if random.random() < 0.65:
                    new_words.append(random.choice(chitters))
                counter = 0

        if random.random() < 0.4:
            new_words.append(random.choice(chitters))

        return " ".join(new_words)

    # ---------- Webhook Manager ----------
    async def get_or_create_webhook(self, channel: discord.TextChannel):
        """Fetches an existing bot webhook or creates a new one."""
        if channel.id in self.webhook_cache:
            try:
                await self.webhook_cache[channel.id].fetch()
                return self.webhook_cache[channel.id]
            except discord.NotFound:
                del self.webhook_cache[channel.id]

        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.name == "BatEchoBot" and webhook.user == self.bot.user:
                self.webhook_cache[channel.id] = webhook
                return webhook

        webhook = await channel.create_webhook(name="BatEchoBot")
        self.webhook_cache[channel.id] = webhook
        return webhook

    # ---------- Event Listener (Intercepts messages) ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 1. Ignore bots, DMs, and webhook messages
        if message.author.bot:
            return
        if message.guild is None:
            return
        if message.webhook_id is not None:
            return

        # 2. Check the DATABASE to see if this user is toggled in this guild
        if not await self.is_enabled(message.author.id, message.guild.id):
            return

        # 3. Process the message
        webhook = await self.get_or_create_webhook(message.channel)
        altered_text = self.add_bat_chitters(message.content)

        # Delete the original message (requires 'Manage Messages' permission)
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            # Silently fail; if we can't delete, we just send a duplicate
            pass

        # Send the altered message impersonating the user
        await webhook.send(
            content=altered_text,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            allowed_mentions=discord.AllowedMentions.none()
        )

    # ---------- Slash Command (Toggle) ----------
    @app_commands.command(name="bat", description="Toggle bat chittering on a user's messages")
    @app_commands.describe(user="The user to enable/disable bat chittering for")
    @app_commands.guild_only()  # Ensures the command only works in servers
    async def bat(self, interaction: discord.Interaction, user: discord.Member):
        # Prevent toggling on bots or the bot itself
        if user.bot:
            await interaction.response.send_message("🦇 You can't toggle chittering on a bot!", ephemeral=True)
            return
        if user.id == self.bot.user.id:
            await interaction.response.send_message("🦇 I can't chitter at myself!", ephemeral=True)
            return

        # Toggle the user in the database
        new_state = await self.toggle_user(user.id, interaction.guild_id)

        status = "enabled" if new_state else "disabled"
        emoji = "🦇" if new_state else "🦗"

        await interaction.response.send_message(
            f"{emoji} Bat chittering **{status}** for {user.mention}.",
            ephemeral=True
        )

# ---------- Cog Setup ----------
async def setup(bot):
    await bot.add_cog(BatCog(bot))