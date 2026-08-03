

import discord
import random
import sqlite3
from discord.ext import commands
from datetime import datetime, timedelta
database = sqlite3.connect("Krispy.db")
cursor = database.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS Bank (user_id TEXT PRIMARY KEY, kc INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, bi_daily_claimed TIMESTAMP, bi_daily_available TIMESTAMP, claims INTEGER DEFAULT 0)''')


class Fun(commands.Cog):
    def __init__(self,bot):
        self.bot = bot


    @commands.hybrid_command(name="coinflip", description="flip a coin")
    async def coinflop(self,ctx):
        """Flips a coin and returns the result."""
        result = random.choice(["Heads", "Tails"])
        await ctx.send(f"The coin landed on: {result}")

    @commands.hybrid_command(name="prize", description="Open or check your bi-daily gift")
    async def prize(self, ctx):
        user_id = str(ctx.author.id)
        cursor.execute("SELECT * FROM Bank WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if user_data is None:
            cursor.execute("INSERT INTO Bank (user_id, kc, streak, bi_daily_claimed, bi_daily_available, claims) VALUES (?, ?, ?, ?, ?, ?)", (user_id, 0, 0, None, None, 0))
            database.commit()
            await ctx.send("You have been added to the bank! Use the command again to check your prize.")
        else:
            bi_daily = 50
            current_time = datetime.now()
            bi_daily_claimed = user_data[3]
            bi_daily_available = user_data[4]
            new_hi_low_streak = user_data[2]
            claims = user_data[5]
            if bi_daily_claimed:
                bi_daily_claimed = datetime.fromisoformat(bi_daily_claimed)
                if bi_daily_available:
                    bi_daily_available = datetime.fromisoformat(bi_daily_available)
    
    
        if bi_daily_available is None or current_time >= bi_daily_available:
        
            view = discord.ui.View()
            claim_button = discord.ui.Button(label="🎁 Claim Prize", style=discord.ButtonStyle.green)
        
            async def claim_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This isn't your prize!", ephemeral=True)
                    return
            
                bonus = min(claims * 5, 50)
                total_reward = bi_daily + bonus
                new_balance = user_data[1] + total_reward
                new_streak = claims + 1
                next_available = current_time + timedelta(hours=12)
                
            
                cursor.execute(
                    "UPDATE Bank SET kc = ?, streak = ?, bi_daily_claimed = ?, bi_daily_available = ?, claims = ? WHERE user_id = ?",
                    (new_balance, new_hi_low_streak, current_time.isoformat(), next_available.isoformat(), new_streak, user_id)
                )
                database.commit()
            
                await interaction.response.edit_message(
                    content=f"🎁 You claimed your bi-daily prize of **{total_reward} KC**! (Base: {bi_daily} + Bonus: {bonus} from streak)\nNext prize available: <t:{int(next_available.timestamp())}:R>",
                    view=None
                )
        
            claim_button.callback = claim_callback
            view.add_item(claim_button)
        
            await ctx.send(f"💰 Your bi-daily prize is ready! (Base: {bi_daily} KC)\nStreak bonus: +{min(claims * 5, 50)} KC\nClick the button to claim!", view=view)
        else:
            time_remaining = bi_daily_available - current_time
            hours = int(time_remaining.total_seconds() // 3600)
            minutes = int((time_remaining.total_seconds() % 3600) // 60)
        
            await ctx.send(f"⏰ You've already claimed your prize! Next available in **{hours}h {minutes}m**.\nCurrent streak: {claims}")



async def setup(bot):
    await bot.add_cog(Fun(bot))