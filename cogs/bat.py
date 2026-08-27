import discord
from discord.ext import commands
from discord import app_commands
import random
import aiosqlite          # <-- added
import asyncio

class BatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "Krispy.db"
        self.webhook_cache = {}

    async def cog_load(self):
        await self.init_db()

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bat_users (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            await db.commit()

    async def is_enabled(self, user_id: int, guild_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT enabled FROM bat_users WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None and bool(row[0])

    async def toggle_user(self, user_id: int, guild_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT enabled FROM bat_users WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()

            if row is None:
                new_state = 1
                await db.execute(
                    'INSERT INTO bat_users (user_id, guild_id, enabled) VALUES (?, ?, ?)',
                    (user_id, guild_id, new_state)
                )
            else:
                new_state = 1 - row[0]
                await db.execute(
                    'UPDATE bat_users SET enabled = ? WHERE user_id = ? AND guild_id = ?',
                    (new_state, user_id, guild_id)
                )

            await db.commit()
            return bool(new_state)

    def add_bat_chitters(self, text: str) -> str:
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return
        if message.webhook_id is not None:
            return

        if not await self.is_enabled(message.author.id, message.guild.id):
            return

        webhook = await self.get_or_create_webhook(message.channel)
        altered_text = self.add_bat_chitters(message.content)

        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

        await webhook.send(
            content=altered_text,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            allowed_mentions=discord.AllowedMentions.none()
        )

    @app_commands.command(name="bat", description="Toggle bat chittering on a user's messages")
    @app_commands.describe(user="The user to enable/disable bat chittering for")
    @app_commands.guild_only()
    async def bat(self, interaction: discord.Interaction, user: discord.Member):
        if user.bot:
            await interaction.response.send_message("🦇 You can't toggle chittering on a bot!", ephemeral=True)
            return
        if user.id == self.bot.user.id:
            await interaction.response.send_message("🦇 I can't chitter at myself!", ephemeral=True)
            return

        new_state = await self.toggle_user(user.id, interaction.guild_id)

        status = "enabled" if new_state else "disabled"
        emoji = "🦇" if new_state else "🦗"

        await interaction.response.send_message(
            f"{emoji} Bat chittering **{status}** for {user.mention}.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(BatCog(bot))