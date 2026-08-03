import discord
import random
from discord.ext import commands


class Fun(commands.Cog):
    def __init__(self,bot):
        self.bot = bot


    @commands.hybrid_command(name="coinflip", description="flip a coin")
    async def coinflop(self,ctx):
        """Flips a coin and returns the result."""
        result = random.choice(["Heads", "Tails"])
        await ctx.send(f"The coin landed on: {result}")


async def setup(bot):
    await bot.add_cog(Fun(bot))