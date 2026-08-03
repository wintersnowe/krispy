import os
import discord
from discord.ext import commands
import datetime
import asyncio
import sqlite3
import time
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Optional


load_dotenv()
TOKEN = os.getenv("TOKEN")
database = sqlite3.connect("Krispy.db")
cursor = database.cursor()



intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class BootAnimator:
    def __init__(self):
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current_frame = 0
        self.start_time = time.time()

    def get_spinner(self) -> str:
        frame = self.spinner_frames[self.current_frame]
        self.current_frame = (self.current_frame + 1) % len(self.spinner_frames)
        return frame

    def elapsed_time(self) -> str:
        return f"{time.time() - self.start_time:.2f}s"

    async def print_loading_step(self, text: str, status: Optional[str] = None, color: str = "cyan"):
        spinner = self.get_spinner()
        elapsed = self.elapsed_time()
        
        colors = {
            "cyan": "\033[96m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "reset": "\033[0m"
        }
        
        status_text = ""
        if status:
            status_color = "green" if status.lower() == "success" else "red" if status.lower() == "failed" else "yellow"
            status_text = f" [{colors[status_color]}{status.upper()}{colors['reset']}]"
        
        print(f"{colors[color]}{spinner} [{elapsed}] {text}{status_text}{colors['reset']}")
        await asyncio.sleep(0.1)



class Krispy(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    async def setup_hook(self):
        """Load extensions from cogs/"""
        animator = BootAnimator()


        EXT_FOLDERS = ("cogs",)
        for folder in EXT_FOLDERS:
            if os.path.exists(folder):
                await animator.print_loading_step(f"Scanning {folder} for extensions...")
                for filename in os.listdir(folder):
                    if filename.endswith(".py") and not filename.startswith("__"):
                        module_name = filename[:-3]
                        if module_name.isidentifier() and folder.isidentifier():
                            import_path = f"{folder}.{module_name}"
                            try:
                                await animator.print_loading_step(f"Loading {import_path}...")
                                await self.load_extension(import_path)
                            except Exception as e:
                                await animator.print_loading_step(f"Failed to load {import_path}", "FAILED", "red")
                                print(f"Error loading {import_path}: {e}")

bot = Krispy(command_prefix="$", intents=intents)

@bot.event
async def on_ready():
    animator = BootAnimator()
    
    
    steps = [
        ("Syncing slash commands...", bot.tree.sync()),
        ("Setting status...", await bot.change_presence(activity=discord.Game(name="Rebranding soon. . ."))),
        ("Finalizing startup...", None),
    ]

    for text, task in steps:
        try:
            await animator.print_loading_step(text)
            if task is not None:
                await task
            await animator.print_loading_step(text, "SUCCESS")
        except Exception as e:
            await animator.print_loading_step(text, "FAILED", "red")
            print(f"Error during startup step '{text}': {e}")
            raise

    print(f'\n\033[92m[READY]\033[0m Logged in as {bot.user} (ID: {bot.user.id} :p)')  # type: ignore
    print(f'\033[94m[INFO]\033[0m Boot completed in {animator.elapsed_time()}')
    print('\033[94m[INFO]\033[0m ' + '=' * 40)

if __name__ == "__main__":
    bot.run(TOKEN)