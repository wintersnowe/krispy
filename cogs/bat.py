import discord
from discord.ext import commands
from discord import app_commands
import random
import aiosqlite
import re

class BatUwuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "Krispy.db"
        self.webhook_cache = {}

    async def cog_load(self):
        await self.init_db()

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_modes (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    bat_enabled INTEGER NOT NULL DEFAULT 0,
                    uwu_enabled INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            await db.commit()

    # ---------- Database Helpers ----------
    async def is_enabled(self, user_id: int, guild_id: int, mode: str) -> bool:
        """Check if a specific mode is enabled for the user in this guild."""
        async with aiosqlite.connect(self.db_path) as db:
            column = "bat_enabled" if mode == "bat" else "uwu_enabled"
            async with db.execute(
                f'SELECT {column} FROM user_modes WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None and bool(row[0])

    async def toggle_user(self, user_id: int, guild_id: int, mode: str) -> bool:
        """Toggle the specified mode and return the new state."""
        column = "bat_enabled" if mode == "bat" else "uwu_enabled"
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f'SELECT {column} FROM user_modes WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()

            if row is None:
                # Insert with this mode enabled, others default 0
                if mode == "bat":
                    await db.execute(
                        'INSERT INTO user_modes (user_id, guild_id, bat_enabled, uwu_enabled) VALUES (?, ?, 1, 0)',
                        (user_id, guild_id)
                    )
                else:
                    await db.execute(
                        'INSERT INTO user_modes (user_id, guild_id, bat_enabled, uwu_enabled) VALUES (?, ?, 0, 1)',
                        (user_id, guild_id)
                    )
                new_state = 1
            else:
                new_state = 1 - row[0]
                await db.execute(
                    f'UPDATE user_modes SET {column} = ? WHERE user_id = ? AND guild_id = ?',
                    (new_state, user_id, guild_id)
                )

            await db.commit()
            return bool(new_state)

    # ---------- Text Transformers ----------
    def add_bat_chitters(self, text: str) -> str:
        """Insert bat sounds randomly."""
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
            if counter >= random.randint(2, 6):
                if random.random() < 0.75:
                    new_words.append(random.choice(chitters))
                counter = 0
        if random.random() < 0.45:
            new_words.append(random.choice(chitters))
        return " ".join(new_words)

    def uwuify_text(self, text: str) -> str:
        """A simple uwu transformation (you can make it fancier)."""
        if not text:
            return "*uwu*"
        # Replace some patterns
        text = re.sub(r'[rl]', 'w', text)
        text = re.sub(r'[RL]', 'W', text)
        text = re.sub(r'n([aeiou])', r'ny\1', text)
        text = re.sub(r'N([aeiou])', r'Ny\1', text)
        # Add occasional uwu
        if random.random() < 0.35:
            text += " uwu"
        return text

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
            if webhook.name == "BatEchoBot" and webhook.user == self.bot.user:
                self.webhook_cache[channel.id] = webhook
                return webhook

        webhook = await channel.create_webhook(name="BatEchoBot")
        self.webhook_cache[channel.id] = webhook
        return webhook

    # ---------- Event Listener ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or message.webhook_id is not None:
            return

        user_id = message.author.id
        guild_id = message.guild.id

        # Check both modes
        bat_on = await self.is_enabled(user_id, guild_id, "bat")
        uwu_on = await self.is_enabled(user_id, guild_id, "uwu")
        if not bat_on and not uwu_on:
            return
        content = message.content.strip()
        if not content:
            return
        link_pattern = re.compile(r'^https?://\S+$')
        if link_pattern.match(content):
            return

        # Start with original content
        altered_text = message.content

        # Apply bat if enabled
        if bat_on:
            altered_text = self.add_bat_chitters(altered_text)

        # Apply uwu if enabled (order doesn't matter much)
        if uwu_on:
            altered_text = self.uwuify_text(altered_text)

        # If both are off (shouldn't happen), just skip
        if altered_text == message.content and not (bat_on or uwu_on):
            return

        webhook = await self.get_or_create_webhook(message.channel)

        # Delete original
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Send altered message
        await webhook.send(
            content=altered_text,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            allowed_mentions=discord.AllowedMentions.none()
        )

    # ---------- Slash Commands ----------
    @app_commands.command(name="bat", description="Toggle bat chittering on a user's messages")
    @app_commands.describe(user="The user to enable/disable bat chittering for")
    @app_commands.guild_only()
    async def bat(self, interaction: discord.Interaction, user: discord.Member):
        if user.bot or user.id == self.bot.user.id:
            await interaction.response.send_message("🦇 That user can't be toggled.", ephemeral=True)
            return

        new_state = await self.toggle_user(user.id, interaction.guild_id, "bat")
        status = "enabled" if new_state else "disabled"
        await interaction.response.send_message(
            f"{'🦇' if new_state else '🦗'} Bat chittering **{status}** for {user.mention}.",
            ephemeral=True
        )

    @app_commands.command(name="uwuify", description="Uwuify a user's messages")
    @app_commands.describe(user="The user to enable/disable uwu for")
    @app_commands.guild_only()
    async def uwuify(self, interaction: discord.Interaction, user: discord.Member):
        if user.bot or user.id == self.bot.user.id:
            await interaction.response.send_message("😤 That user can't be toggled.", ephemeral=True)
            return

        new_state = await self.toggle_user(user.id, interaction.guild_id, "uwu")
        status = "enabled" if new_state else "disabled"
        await interaction.response.send_message(
            f"{'😊' if new_state else '😶'} Uwuification **{status}** for {user.mention}.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(BatUwuCog(bot))