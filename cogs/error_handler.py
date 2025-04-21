import discord
from discord.ext import commands
import traceback
import sys
import logging
from discord import app_commands

from utils import create_embed

logger = logging.getLogger(__name__)

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.on_error = self.on_app_command_error
    
    # Handle regular command errors
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command."""
        
        # Get the original exception
        error = getattr(error, 'original', error)
        
        # If command has local error handler, return
        if hasattr(ctx.command, 'on_error'):
            return
        
        # Get the cog
        cog = ctx.cog
        
        # If cog has error handler, return
        if cog and cog._get_overridden_method(cog.cog_command_error) is not None:
            return
        
        # Process the error
        await self._handle_error(ctx, error)
    
    # Handle application command (slash command) errors
    async def on_app_command_error(self, interaction, error):
        """The event triggered when an error is raised while invoking an application command."""
        
        # Get the original exception
        error = getattr(error, 'original', error)
        
        # Process the error
        await self._handle_app_command_error(interaction, error)
    
    async def _handle_app_command_error(self, interaction, error):
        """Handle errors for application commands."""
        
        if isinstance(error, app_commands.CommandOnCooldown):
            # Handle cooldown
            seconds = round(error.retry_after)
            message = f"This command is on cooldown. Please wait {seconds} second(s) before using it again."
            
            try:
                # Try to respond if interaction is not already responded to
                if not interaction.response.is_done():
                    await interaction.response.send_message(message, ephemeral=True)
                else:
                    await interaction.followup.send(message, ephemeral=True)
            except Exception:
                pass
            
            return
        
        elif isinstance(error, app_commands.MissingPermissions):
            # Handle missing permissions
            message = "You don't have the required permissions to use this command."
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(message, ephemeral=True)
                else:
                    await interaction.followup.send(message, ephemeral=True)
            except Exception:
                pass
            
            return
        
        elif isinstance(error, discord.Forbidden):
            # Handle bot missing permissions
            message = "I don't have the required permissions to perform this action."
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(message, ephemeral=True)
                else:
                    await interaction.followup.send(message, ephemeral=True)
            except Exception:
                pass
            
            return
        
        # For all other errors
        error_embed = create_embed(
            title="Command Error",
            description="An error occurred while running this command. The error has been logged.",
            color=discord.Color.red().value
        )
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
        except Exception:
            pass
        
        # Log the error
        logger.error(f"Application command error in {interaction.command.name}:")
        logger.error(''.join(traceback.format_exception(type(error), error, error.__traceback__)))
    
    async def _handle_error(self, ctx, error):
        """Handle common errors for regular commands."""
        
        if isinstance(error, commands.CommandNotFound):
            # Silently ignore command not found errors
            return
        
        elif isinstance(error, commands.CommandOnCooldown):
            # Handle cooldown
            seconds = round(error.retry_after)
            await ctx.send(f"This command is on cooldown. Please wait {seconds} second(s) before using it again.")
            return
        
        elif isinstance(error, commands.MissingPermissions):
            # Handle missing permissions
            await ctx.send("You don't have the required permissions to use this command.")
            return
        
        elif isinstance(error, commands.BotMissingPermissions):
            # Handle bot missing permissions
            await ctx.send("I don't have the required permissions to perform this action.")
            return
        
        elif isinstance(error, commands.MissingRequiredArgument):
            # Handle missing arguments
            await ctx.send(f"Missing required argument: {error.param.name}")
            return
        
        elif isinstance(error, discord.Forbidden):
            # Handle Discord forbidden errors
            await ctx.send("I don't have the required permissions to perform this action.")
            return
        
        # For all other errors, log them
        logger.error(f"Command error in {ctx.command}:")
        logger.error(''.join(traceback.format_exception(type(error), error, error.__traceback__)))
        
        # Send an error message
        error_embed = create_embed(
            title="Command Error",
            description="An error occurred while running this command. The error has been logged.",
            color=discord.Color.red().value
        )
        
        await ctx.send(embed=error_embed)

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot)) 