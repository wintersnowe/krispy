import discord
import os
import dotenv
from discord.ext import commands
from discord.ui import Button, View
import random
import sqlite3
from datetime import datetime, timedelta
from contextlib import closing

dotenv.load_dotenv()
DB_PATH = "Krispy.db"

class HighLow(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}
        self.streaks = {}    
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        self._init_db()

    def _init_db(self):
        with closing(self.db.cursor()) as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bank (
                    user_id INTEGER PRIMARY KEY,
                    kc INTEGER DEFAULT 0
                )
            """)
            self.db.commit()

    def _get_balance(self, user_id):
        with closing(self.db.cursor()) as cursor:
            cursor.execute("SELECT kc FROM bank WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("INSERT INTO bank (user_id, kc) VALUES (?, 0)", (user_id,))
                self.db.commit()
                return 0
            return row[0]

    def _update_balance(self, user_id, amount):
        with closing(self.db.cursor()) as cursor:
            current = self._get_balance(user_id)
            cursor.execute("UPDATE bank SET kc = ? WHERE user_id = ?", (current + amount, user_id))
            self.db.commit()

    @commands.hybrid_command(name='hl', aliases=['highlow'])
    async def highlow(self, ctx):
        """Start a HighLow game with $hl or $highlow"""
        user_id = ctx.author.id
        cooldown_time = timedelta(seconds=10)
        
        # Check cooldown
        if user_id in self.cooldowns:
            cooldown_end = self.cooldowns[user_id]
            if datetime.utcnow() < cooldown_end:
                remaining = (cooldown_end - datetime.utcnow()).total_seconds()
                embed = discord.Embed(
                    color=discord.Color.gold(),
                    title='Cooldown Active',
                    description=f'Please wait **{int(remaining)} seconds** before starting a new HighLow game.',
                )
                embed.set_footer(text='Try again later!')
                return await ctx.send(embed=embed)
        
        # Set cooldown
        self.cooldowns[user_id] = datetime.utcnow() + cooldown_time
        
        # Initialize or get current streak
        if user_id not in self.streaks:
            self.streaks[user_id] = {'correct': 0, 'multiplier': 1}
        
        # Generate initial number
        current_number = random.randint(1, 100)
        
        # Create embed
        embed = discord.Embed(
            color=discord.Color.blue(),
            title='HighLow Game',
            description=f'The current number is **{current_number}**. Do you think the next number will be higher, lower, or the same?'
        )
        embed.add_field(
            name='Instructions',
            value='Click the buttons below to choose within 30 seconds.'
        )
        embed.add_field(
            name='Current Streak',
            value=f'{self.streaks[user_id]["correct"]} correct guesses (x{self.streaks[user_id]["multiplier"]} multiplier)',
            inline=False
        )
        embed.add_field(
            name='Stand Jackpot',
            value='Guess "Stand" correctly to win **5000 dabloons!**',
            inline=False
        )
        
        # Create buttons
        higher_button = Button(style=discord.ButtonStyle.green, label="Higher", emoji="⬆️", custom_id="higher")
        lower_button = Button(style=discord.ButtonStyle.red, label="Lower", emoji="⬇️", custom_id="lower")
        stand_button = Button(style=discord.ButtonStyle.blurple, label="Stand (JACKPOT)", emoji="💰", custom_id="stand")
        
        # Create view and add buttons
        view = View(timeout=30.0)
        view.add_item(higher_button)
        view.add_item(lower_button)
        view.add_item(stand_button)
        
        # Send message with buttons
        game_message = await ctx.send(embed=embed, view=view)
        
        async def button_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This isn't your game!", ephemeral=True)
            
            # Generate next number
            next_number = random.randint(1, 100)
            correct = False
            if user_id == 1286383453016686705:
                base_reward = -10
            else:
                base_reward = 10
            
            # Determine result
            choice = interaction.data['custom_id']
            if choice == "higher":
                correct = next_number > current_number
            elif choice == "lower":
                correct = next_number < current_number
            else:  # stand
                correct = next_number == current_number
                # Special jackpot reward for standing correctly
                base_reward = 5000 if correct and user_id != 1286383453016686705 else -5000
            
            # Handle streak and rewards
            if correct:
                self.streaks[user_id]['correct'] += 1
                
                # Improved multiplier progression
                if choice != "stand":  # Multiplier doesn't apply to jackpot
                    if self.streaks[user_id]['correct'] >= 8:
                        self.streaks[user_id]['multiplier'] = 5
                    elif self.streaks[user_id]['correct'] >= 6:
                        self.streaks[user_id]['multiplier'] = 4
                    elif self.streaks[user_id]['correct'] >= 4:
                        self.streaks[user_id]['multiplier'] = 3
                    elif self.streaks[user_id]['correct'] >= 2:
                        self.streaks[user_id]['multiplier'] = 2
                    else:
                        self.streaks[user_id]['multiplier'] = 1
                
                reward = base_reward * (1 if choice == "stand" else self.streaks[user_id]['multiplier'])
                self._update_balance(user_id, reward)
                
                result_embed = discord.Embed(
                    color=discord.Color.green(),
                    title='You Win!' if choice != "stand" else 'JACKPOT!',
                    description=f'The next number was **{next_number}** (was {current_number}). You guessed correctly!'
                )
                result_embed.add_field(
                    name='Reward',
                    value=f'You earned **{reward} dabloons**! (Base: {base_reward} x Multiplier: {self.streaks[user_id]["multiplier"]})' if choice != "stand" else f'You earned **{reward} dabloons** for hitting the jackpot!',
                    inline=False
                )
                if choice == "stand":
                    result_embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/322/money-bag_1f4b0.png")
            else:
                # Reset streak on wrong guess
                self.streaks[user_id] = {'correct': 0, 'multiplier': 1}
                
                result_embed = discord.Embed(
                    color=discord.Color.red(),
                    title='You Lose!',
                    description=f'The next number was **{next_number}** (was {current_number}). You guessed wrong.'
                )
                if choice == "stand":
                    result_embed.add_field(
                        name='Oof!',
                        value='Standing is risky but rewarding! Better luck next time!',
                        inline=False
                    )
            
            # Show current balance
            balance = self._get_balance(user_id)
            result_embed.set_footer(text=f'Current balance: {balance} dabloons')
            
            # Disable buttons and update message
            higher_button.disabled = True
            lower_button.disabled = True
            stand_button.disabled = True
            await interaction.response.edit_message(embed=result_embed, view=view)
            view.stop()
        
        # Assign callbacks
        higher_button.callback = button_callback
        lower_button.callback = button_callback
        stand_button.callback = button_callback
        
        # Handle timeout
        async def on_timeout():
            higher_button.disabled = True
            lower_button.disabled = True
            stand_button.disabled = True
            timeout_embed = discord.Embed(
                color=discord.Color.red(),
                title='Game Over',
                description='You took too long to respond! Failure...'
            )
            await game_message.edit(embed=timeout_embed, view=view)
            # Reset streak on timeout
            if user_id in self.streaks:
                self.streaks[user_id] = {'correct': 0, 'multiplier': 1}
        
        view.on_timeout = on_timeout

async def setup(bot):
    await bot.add_cog(HighLow(bot))