import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

# Set up intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

# Initialize bot with command prefix and intents
class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            application_id=os.getenv('CLIENT_ID')
        )
        self.initial_extensions = [
            'cogs.tickets',
            'cogs.ticket_management',
            'cogs.error_handler',
            'cogs.settings'
        ]
    
    async def setup_hook(self):
        # Load all cogs
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")
        
        # Sync slash commands with Discord
        logger.info("Syncing commands...")
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
    
    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info(f'Connected to {len(self.guilds)} guilds')
        activity = discord.Activity(type=discord.ActivityType.watching, name="for tickets")
        await self.change_presence(activity=activity)

# Create bot instance
bot = TicketBot()

# Run the bot
async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main()) 