import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from typing import Optional, List, Dict, Any
import logging
import os
import sys
from pathlib import Path
import datetime

# Add project root to path if needed
sys.path.append(str(Path(__file__).parent.parent))

from config import config
from utils import create_embed, generate_transcript, save_transcript, search_transcripts, format_search_results

logger = logging.getLogger(__name__)

# Confirmation view for closing or deleting tickets
class ConfirmationView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60)  # 1 minute timeout
        self.value = None
        self.author_id = author_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        try:
            await interaction.response.defer()
        except:
            pass  # Ignore errors if already deferred
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        try:
            await interaction.response.defer()
        except:
            pass  # Ignore errors if already deferred
        self.stop()

# View for displaying and interacting with transcript search results
class TranscriptResultsView(discord.ui.View):
    def __init__(self, results: List[Dict[str, Any]], bot):
        super().__init__(timeout=300)  # 5 minute timeout
        self.results = results
        self.bot = bot
        self.add_result_buttons()
    
    def add_result_buttons(self):
        # Add a button for each result (up to 10)
        for i, result in enumerate(self.results[:10]):
            # Create a button with the index+1 as the label
            button = discord.ui.Button(
                label=f"{i+1}", 
                style=discord.ButtonStyle.primary,
                custom_id=f"transcript_{i}"
            )
            button.callback = self.create_callback(i)
            self.add_item(button)
    
    def create_callback(self, index):
        async def button_callback(interaction: discord.Interaction):
            if index >= len(self.results):
                await interaction.response.send_message("Invalid selection.", ephemeral=True)
                return
            
            result = self.results[index]
            file_path = result.get("path")
            
            if not file_path or not os.path.exists(file_path):
                await interaction.response.send_message("Transcript file not found.", ephemeral=True)
                return
            
            try:
                # Indicate that we're processing
                await interaction.response.defer(ephemeral=True)
                
                # Send the file
                await interaction.followup.send(
                    f"Here is the transcript from {result.get('date', 'unknown date')}:",
                    file=discord.File(file_path),
                    ephemeral=True
                )
            except Exception as e:
                logging.error(f"Error sending transcript file: {e}")
                await interaction.followup.send(
                    "An error occurred while retrieving the transcript file.",
                    ephemeral=True
                )
        
        return button_callback

# Button UI for common ticket actions
class TicketActionsView(discord.ui.View):
    def __init__(self, ticket_manager, channel_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.ticket_manager = ticket_manager
        self.channel_id = channel_id
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close_button")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Call the close ticket command
        await interaction.response.defer()
        await self.ticket_manager.handle_close_button(interaction)
    
    @discord.ui.button(label="Generate Transcript", style=discord.ButtonStyle.primary, emoji="📝", custom_id="ticket_transcript_button")
    async def transcript_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Call the transcript command
        await interaction.response.defer()
        await self.ticket_manager.handle_transcript_button(interaction)

class TicketManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def is_ticket_channel(self, channel_id: int) -> bool:
        """Check if a channel is a ticket channel"""
        return config.get_ticket(channel_id) is not None
    
    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if the user has permission to manage tickets"""
        # Administrators always have permission
        if interaction.user.guild_permissions.administrator:
            return True
        
        # Check if the user has a staff role
        staff_role_ids = config.get("staff_role_ids", [])
        for role in interaction.user.roles:
            if role.id in staff_role_ids:
                return True
        
        # Check if the user is the ticket creator
        ticket_info = config.get_ticket(interaction.channel.id)
        if ticket_info and ticket_info.get("user_id") == interaction.user.id:
            return True
        
        return False
    
    async def safe_response(self, interaction, content=None, **kwargs):
        """Safely respond to an interaction, handling cases where it's already been responded to"""
        try:
            if not interaction.response.is_done():
                if content:
                    await interaction.response.send_message(content, **kwargs)
                else:
                    await interaction.response.send_message(**kwargs)
            else:
                if content:
                    await interaction.followup.send(content, **kwargs)
                else:
                    await interaction.followup.send(**kwargs)
        except discord.errors.HTTPException as e:
            if e.code != 40060:  # If not "already acknowledged"
                logger.error(f"HTTP error responding to interaction: {e}")
        except discord.errors.NotFound:
            logger.warning("Attempted to respond to an expired interaction")
        except Exception as e:
            logger.error(f"Error responding to interaction: {e}")
    
    @app_commands.command(name="ticket_add", description="Add a user to the current ticket")
    @app_commands.describe(user="The user to add to the ticket")
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.channel_id)  # 1 use per 10 seconds per channel
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        try:
            # Check if this is a ticket channel
            if not self.is_ticket_channel(interaction.channel.id):
                return await self.safe_response(
                    interaction,
                    "This command can only be used in a ticket channel.",
                    ephemeral=True
                )
            
            # Check permissions
            if not await self.check_permissions(interaction):
                return await self.safe_response(
                    interaction,
                    "You don't have permission to add users to this ticket.",
                    ephemeral=True
                )
            
            # Add the user to the channel
            try:
                await interaction.channel.set_permissions(
                    user,
                    read_messages=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True
                )
                
                # Send confirmation
                await self.safe_response(
                    interaction,
                    f"Added {user.mention} to the ticket.",
                    ephemeral=False
                )
                
            except discord.Forbidden:
                await self.safe_response(
                    interaction,
                    "I don't have permission to modify channel permissions.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error in ticket_add command: {e}")
            await self.safe_response(
                interaction,
                "An error occurred while processing your command.",
                ephemeral=True
            )
    
    @app_commands.command(name="ticket_remove", description="Remove a user from the current ticket")
    @app_commands.describe(user="The user to remove from the ticket")
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.channel_id)  # 1 use per 10 seconds per channel
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        try:
            # Check if this is a ticket channel
            if not self.is_ticket_channel(interaction.channel.id):
                return await self.safe_response(
                    interaction,
                    "This command can only be used in a ticket channel.",
                    ephemeral=True
                )
            
            # Check permissions
            if not await self.check_permissions(interaction):
                return await self.safe_response(
                    interaction,
                    "You don't have permission to remove users from this ticket.",
                    ephemeral=True
                )
            
            # Prevent removing ticket owner
            ticket_info = config.get_ticket(interaction.channel.id)
            if ticket_info and int(ticket_info.get("user_id")) == user.id:
                return await self.safe_response(
                    interaction,
                    "You cannot remove the ticket creator from the ticket.",
                    ephemeral=True
                )
            
            # Remove the user from the channel
            try:
                await interaction.channel.set_permissions(user, overwrite=None)
                
                # Send confirmation
                await self.safe_response(
                    interaction,
                    f"Removed {user.mention} from the ticket.",
                    ephemeral=False
                )
                
            except discord.Forbidden:
                await self.safe_response(
                    interaction,
                    "I don't have permission to modify channel permissions.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error in ticket_remove command: {e}")
            await self.safe_response(
                interaction,
                "An error occurred while processing your command.",
                ephemeral=True
            )
    
    @app_commands.command(name="ticket_close", description="Close the current ticket")
    @app_commands.checks.cooldown(1, 20, key=lambda i: i.channel_id)  # 1 use per 20 seconds per channel
    async def ticket_close(self, interaction: discord.Interaction):
        try:
            # Check if this is a ticket channel
            if not self.is_ticket_channel(interaction.channel.id):
                return await self.safe_response(
                    interaction,
                    "This command can only be used in a ticket channel.",
                    ephemeral=True
                )
            
            # Check permissions
            if not await self.check_permissions(interaction):
                return await self.safe_response(
                    interaction,
                    "You don't have permission to close this ticket.",
                    ephemeral=True
                )
            
            # Check if ticket is already closed
            ticket_info = config.get_ticket(interaction.channel.id)
            if ticket_info and ticket_info.get("status") == "closed":
                return await self.safe_response(
                    interaction,
                    "This ticket is already closed.",
                    ephemeral=True
                )
            
            # Confirm closing the ticket
            embed = create_embed(
                title="Close Ticket",
                description="Are you sure you want to close this ticket? This will archive the channel and generate an HTML transcript.",
                color=discord.Color.orange().value
            )
            
            view = ConfirmationView(interaction.user.id)
            await self.safe_response(interaction, embed=embed, view=view, ephemeral=True)
            
            # Wait for confirmation
            await view.wait()
            
            if view.value:
                # Get ticket info
                ticket_info = config.get_ticket(interaction.channel.id)
                user_id = int(ticket_info.get("user_id", 0))
                user = interaction.guild.get_member(user_id)
                
                # Get transcript channel if configured
                transcript_channel_id = config.get("transcript_channel_id")
                transcript_channel = None
                if transcript_channel_id:
                    try:
                        transcript_channel = interaction.guild.get_channel(int(transcript_channel_id))
                    except:
                        logger.error(f"Failed to get transcript channel with ID {transcript_channel_id}")
                
                # Generate transcript if transcript channel is configured
                transcript_file_path = None
                if transcript_channel:
                    await interaction.channel.send("Generating HTML transcript...")
                    try:
                        transcript_text = await generate_transcript(interaction.channel, format_type="html")
                        transcript_file_path = await save_transcript(transcript_text, interaction.channel.id)
                        
                        # Send to transcript channel
                        if transcript_file_path and os.path.exists(transcript_file_path):
                            user_mention = f"<@{user_id}>" if user else "Unknown user"
                            
                            message_content = (
                                f"HTML Transcript for ticket {interaction.channel.name} (ticket closed)\n"
                                f"Closed by: {interaction.user.mention}\n"
                                f"Ticket creator: {user_mention}\n"
                                f"Closed on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"Format: HTML with enhanced styling"
                            )
                            
                            await transcript_channel.send(
                                message_content,
                                file=discord.File(transcript_file_path)
                            )
                            
                            # Notify in ticket channel
                            await interaction.channel.send(f"HTML transcript has been sent to {transcript_channel.mention}.")
                    except Exception as e:
                        logger.error(f"Error generating transcript: {e}")
                        await interaction.channel.send("Failed to generate transcript.")
                else:
                    await interaction.channel.send("No transcript channel is configured. Closing ticket without generating transcript.")
                
                # Update ticket status
                config.update_ticket_status(interaction.channel.id, "closed")
                
                # Create closed embed
                closed_embed = create_embed(
                    title="Ticket Closed",
                    description=f"This ticket has been closed by {interaction.user.mention}.",
                    color=discord.Color.red().value
                )
                
                # Send closing message
                await interaction.channel.send(embed=closed_embed)
                
                # Revoke permissions for the ticket creator
                if user:
                    try:
                        await interaction.channel.set_permissions(user, overwrite=None)
                    except:
                        pass
                
                # Update channel name to show it's closed
                try:
                    await interaction.channel.edit(name=f"{interaction.channel.name}-closed")
                except discord.Forbidden:
                    pass  # Ignore if we can't rename
                
            elif view.value is False:
                try:
                    await interaction.followup.send("Ticket closure cancelled.", ephemeral=True)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error in ticket_close command: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred while processing your command.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred while processing your command.", ephemeral=True)
            except:
                pass
    
    @app_commands.command(name="ticket_delete", description="Delete the current ticket")
    @app_commands.checks.cooldown(1, 30, key=lambda i: i.channel_id)  # 1 use per 30 seconds per channel
    async def ticket_delete(self, interaction: discord.Interaction):
        try:
            # Check if this is a ticket channel
            if not self.is_ticket_channel(interaction.channel.id):
                return await self.safe_response(
                    interaction,
                    "This command can only be used in a ticket channel.",
                    ephemeral=True
                )
            
            # Check permissions
            if not await self.check_permissions(interaction):
                return await self.safe_response(
                    interaction,
                    "You don't have permission to delete this ticket.",
                    ephemeral=True
                )
            
            # Confirm deletion
            embed = create_embed(
                title="Delete Ticket",
                description="Are you sure you want to delete this ticket? This will permanently delete the channel and cannot be undone.",
                color=discord.Color.red().value
            )
            
            view = ConfirmationView(interaction.user.id)
            await self.safe_response(interaction, embed=embed, view=view, ephemeral=True)
            
            # Wait for confirmation
            await view.wait()
            
            if view.value:
                # Get ticket info before deleting
                ticket_info = config.get_ticket(interaction.channel.id)
                user_id = int(ticket_info.get("user_id", 0))
                user = interaction.guild.get_member(user_id)
                
                # Remove from config
                config.delete_ticket(interaction.channel.id)
                
                # Send notification to user who opened the ticket
                if user:
                    try:
                        user_embed = create_embed(
                            title="Ticket Deleted",
                            description=f"Your ticket in {interaction.guild.name} has been deleted.",
                            color=discord.Color.red().value
                        )
                        await user.send(embed=user_embed)
                    except:
                        pass  # Ignore if we can't DM
                
                # Delete the channel
                try:
                    try:
                        await interaction.followup.send("Deleting ticket channel...", ephemeral=True)
                    except:
                        pass
                    await asyncio.sleep(3)  # Small delay before deletion
                    await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")
                except discord.Forbidden:
                    try:
                        await interaction.followup.send(
                            "I don't have permission to delete this channel.",
                            ephemeral=True
                        )
                    except:
                        pass
            
            elif view.value is False:
                try:
                    await interaction.followup.send("Ticket deletion cancelled.", ephemeral=True)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error in ticket_delete command: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred while processing your command.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred while processing your command.", ephemeral=True)
            except:
                pass
    
    @app_commands.command(name="set_staff", description="Set a role as staff for tickets")
    @app_commands.describe(role="The role to set as staff")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.guild_id)  # 1 use per 10 seconds per guild
    async def set_staff(self, interaction: discord.Interaction, role: discord.Role):
        try:
            # Get current staff roles
            staff_role_ids = config.get("staff_role_ids", [])
            
            # Check if already set
            if role.id in staff_role_ids:
                return await self.safe_response(
                    interaction,
                    f"{role.mention} is already set as a staff role.",
                    ephemeral=True
                )
            
            # Add the role
            staff_role_ids.append(role.id)
            config.set("staff_role_ids", staff_role_ids)
            
            # Confirm
            await self.safe_response(
                interaction,
                f"{role.mention} has been set as a staff role for tickets.",
                ephemeral=False
            )
        except Exception as e:
            logger.error(f"Error in set_staff command: {e}")
            await self.safe_response(
                interaction,
                "An error occurred while processing your command.",
                ephemeral=True
            )
    
    @app_commands.command(name="remove_staff", description="Remove a role from staff for tickets")
    @app_commands.describe(role="The role to remove from staff")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.guild_id)  # 1 use per 10 seconds per guild
    async def remove_staff(self, interaction: discord.Interaction, role: discord.Role):
        try:
            # Get current staff roles
            staff_role_ids = config.get("staff_role_ids", [])
            
            # Check if not set
            if role.id not in staff_role_ids:
                return await self.safe_response(
                    interaction,
                    f"{role.mention} is not a staff role.",
                    ephemeral=True
                )
            
            # Remove the role
            staff_role_ids.remove(role.id)
            config.set("staff_role_ids", staff_role_ids)
            
            # Confirm
            await self.safe_response(
                interaction,
                f"{role.mention} has been removed from staff roles.",
                ephemeral=False
            )
        except Exception as e:
            logger.error(f"Error in remove_staff command: {e}")
            await self.safe_response(
                interaction,
                "An error occurred while processing your command.",
                ephemeral=True
            )

    @app_commands.command(name="transcript", description="Generate a transcript of the current ticket")
    @app_commands.checks.cooldown(1, 30, key=lambda i: i.channel_id)  # 1 use per 30 seconds per channel
    async def generate_transcript_command(self, interaction: discord.Interaction):
        try:
            # Check if this is a ticket channel
            if not self.is_ticket_channel(interaction.channel.id):
                return await self.safe_response(
                    interaction,
                    "This command can only be used in a ticket channel.",
                    ephemeral=True
                )
            
            # Check permissions
            if not await self.check_permissions(interaction):
                return await self.safe_response(
                    interaction,
                    "You don't have permission to generate a transcript.",
                    ephemeral=True
                )
            
            # Initial response
            await self.safe_response(
                interaction,
                "Generating HTML transcript, please wait...",
                ephemeral=False
            )
            
            # Get transcript channel if configured
            transcript_channel_id = config.get("transcript_channel_id")
            transcript_channel = None
            if transcript_channel_id:
                try:
                    transcript_channel = interaction.guild.get_channel(int(transcript_channel_id))
                except:
                    logger.error(f"Failed to get transcript channel with ID {transcript_channel_id}")
            
            # Check if transcript channel is configured
            if not transcript_channel:
                await interaction.channel.send("No transcript channel is configured. Please ask an admin to set one with `/set_transcript_channel`.")
                return
            
            # Generate transcript
            try:
                transcript_text = await generate_transcript(interaction.channel, format_type="html")
                transcript_file_path = await save_transcript(transcript_text, interaction.channel.id)
                
                # Create file to send
                if transcript_file_path and os.path.exists(transcript_file_path):
                    # Send to transcript channel
                    ticket_info = config.get_ticket(interaction.channel.id) or {}
                    user_id = ticket_info.get("user_id", "Unknown")
                    user_mention = f"<@{user_id}>" if user_id != "Unknown" else "Unknown user"
                    
                    message_content = (
                        f"HTML Transcript for ticket {interaction.channel.name} (manual generation)\n"
                        f"Generated by: {interaction.user.mention}\n"
                        f"Ticket creator: {user_mention}\n"
                        f"Format: HTML with enhanced styling"
                    )
                    
                    await transcript_channel.send(
                        message_content,
                        file=discord.File(transcript_file_path)
                    )
                    
                    # Notify in ticket channel that transcript was sent
                    await interaction.channel.send(f"HTML transcript has been sent to {transcript_channel.mention}.")
                    
                    # Log success
                    logger.info(f"HTML transcript generated for channel {interaction.channel.id} by {interaction.user.id}")
                else:
                    # Send failure message
                    await interaction.channel.send("Failed to generate transcript. Please try again.")
                    logger.error(f"Failed to generate transcript for channel {interaction.channel.id}")
            except Exception as e:
                logger.error(f"Error generating transcript: {e}")
                await interaction.channel.send(f"Error generating transcript: {str(e)[:100]}...")
                
        except Exception as e:
            logger.error(f"Error in transcript command: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred while generating the transcript.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred while generating the transcript.", ephemeral=True)
            except:
                pass

    @app_commands.command(name="set_transcript_channel", description="Set channel for ticket transcripts")
    @app_commands.describe(channel="The channel to send ticket transcripts to")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.guild_id)  # 1 use per 10 seconds per guild
    async def set_transcript_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        try:
            # Set the transcript channel
            config.set("transcript_channel_id", channel.id)
            
            # Confirm
            await self.safe_response(
                interaction,
                f"Transcript channel has been set to {channel.mention}. All ticket transcripts will be sent to this channel.",
                ephemeral=False
            )
        except Exception as e:
            logger.error(f"Error in set_transcript_channel command: {e}")
            await self.safe_response(
                interaction,
                "An error occurred while processing your command.",
                ephemeral=True
            )

    @app_commands.command(name="search_transcripts", description="Search through ticket transcripts")
    @app_commands.describe(
        query="Text to search for in transcripts",
        username="Filter by username",
        date_from="Start date in YYYY-MM-DD format",
        date_to="End date in YYYY-MM-DD format"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.guild_id)  # 1 use per 10 seconds per guild
    async def search_transcripts_command(
        self, 
        interaction: discord.Interaction, 
        query: Optional[str] = None,
        username: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ):
        try:
            # Initial response
            await self.safe_response(
                interaction,
                "Searching transcripts, please wait...",
                ephemeral=True
            )
            
            # Validate at least one search parameter
            if not any([query, username, date_from, date_to]):
                return await interaction.followup.send(
                    "Please provide at least one search parameter (query, username, or date range).",
                    ephemeral=True
                )
            
            # Validate date format if provided
            date_error = False
            if date_from:
                try:
                    datetime.datetime.strptime(date_from, "%Y-%m-%d")
                except ValueError:
                    date_error = True
            
            if date_to:
                try:
                    datetime.datetime.strptime(date_to, "%Y-%m-%d")
                except ValueError:
                    date_error = True
            
            if date_error:
                return await interaction.followup.send(
                    "Invalid date format. Please use YYYY-MM-DD format (e.g., 2023-04-15).",
                    ephemeral=True
                )
            
            # Search transcripts
            results = search_transcripts(
                query=query,
                user=username,
                date_from=date_from,
                date_to=date_to,
                limit=50  # Reasonable limit
            )
            
            # Format results for display
            formatted_results = await format_search_results(results)
            
            # Create embed
            embed = create_embed(
                title=formatted_results["title"],
                description=formatted_results["description"],
                fields=formatted_results["fields"],
                color=discord.Color.blue().value
            )
            
            # Create view with transcript buttons if we have results
            if results:
                view = TranscriptResultsView(results[:10], self.bot)  # Limit to 10 for buttons
                await interaction.followup.send(embed=embed, view=view, ephemeral=False)
            else:
                await interaction.followup.send(embed=embed, ephemeral=False)
                
        except Exception as e:
            logger.error(f"Error in search_transcripts command: {e}")
            try:
                await interaction.followup.send(
                    "An error occurred while searching transcripts.",
                    ephemeral=True
                )
            except:
                pass

    @app_commands.command(name="add_ticket_buttons", description="Add ticket action buttons to the current channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.guild_id)  # 1 use per 10 seconds per guild
    async def add_ticket_buttons(self, interaction: discord.Interaction):
        try:
            # Check if this is a ticket channel
            if not self.is_ticket_channel(interaction.channel.id):
                return await self.safe_response(
                    interaction,
                    "This command can only be used in a ticket channel.",
                    ephemeral=True
                )
            
            # Create and send ticket actions view
            embed = create_embed(
                title="Ticket Actions",
                description="Use the buttons below to perform common ticket actions:",
                color=discord.Color.blue().value
            )
            
            view = TicketActionsView(self, interaction.channel.id)
            await interaction.channel.send(embed=embed, view=view)
            
            # Confirmation to user
            await self.safe_response(
                interaction,
                "Ticket action buttons have been added to this channel.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in add_ticket_buttons command: {e}")
            await self.safe_response(
                interaction,
                "An error occurred while adding ticket buttons.",
                ephemeral=True
            )

    async def handle_close_button(self, interaction: discord.Interaction):
        """Handler for ticket close button"""
        # This mimics the ticket_close command but for button interaction
        try:
            # Check if this is a ticket channel
            if not self.is_ticket_channel(interaction.channel.id):
                return await interaction.followup.send(
                    "This button can only be used in a ticket channel.",
                    ephemeral=True
                )
            
            # Check permissions
            if not await self.check_permissions(interaction):
                return await interaction.followup.send(
                    "You don't have permission to close this ticket.",
                    ephemeral=True
                )
            
            # Check if ticket is already closed
            ticket_info = config.get_ticket(interaction.channel.id)
            if ticket_info and ticket_info.get("status") == "closed":
                return await interaction.followup.send(
                    "This ticket is already closed.",
                    ephemeral=True
                )
            
            # Confirm closing the ticket
            embed = create_embed(
                title="Close Ticket",
                description="Are you sure you want to close this ticket? This will archive the channel and generate an HTML transcript.",
                color=discord.Color.orange().value
            )
            
            view = ConfirmationView(interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # Wait for confirmation
            await view.wait()
            
            if view.value:
                # Process similar to ticket_close command
                # Get ticket info
                ticket_info = config.get_ticket(interaction.channel.id)
                user_id = int(ticket_info.get("user_id", 0))
                user = interaction.guild.get_member(user_id)
                
                # Generate transcript with HTML format by default
                transcript_channel_id = config.get("transcript_channel_id")
                transcript_channel = None
                if transcript_channel_id:
                    try:
                        transcript_channel = interaction.guild.get_channel(int(transcript_channel_id))
                    except:
                        logger.error(f"Failed to get transcript channel with ID {transcript_channel_id}")
                
                # Generate transcript if transcript channel is configured
                if transcript_channel:
                    await interaction.channel.send("Generating HTML transcript...")
                    try:
                        transcript_text = await generate_transcript(interaction.channel, format_type="html")
                        transcript_file_path = await save_transcript(transcript_text, interaction.channel.id)
                        
                        # Send to transcript channel
                        if transcript_file_path and os.path.exists(transcript_file_path):
                            user_mention = f"<@{user_id}>" if user else "Unknown user"
                            
                            message_content = (
                                f"HTML Transcript for ticket {interaction.channel.name} (ticket closed)\n"
                                f"Closed by: {interaction.user.mention}\n"
                                f"Ticket creator: {user_mention}\n"
                                f"Closed on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"Format: HTML with enhanced styling"
                            )
                            
                            await transcript_channel.send(
                                message_content,
                                file=discord.File(transcript_file_path)
                            )
                            
                            # Notify in ticket channel
                            await interaction.channel.send(f"HTML transcript has been sent to {transcript_channel.mention}.")
                    except Exception as e:
                        logger.error(f"Error generating transcript: {e}")
                        await interaction.channel.send("Failed to generate transcript.")
                else:
                    await interaction.channel.send("No transcript channel is configured. Closing ticket without generating transcript.")
                
                # Update ticket status
                config.update_ticket_status(interaction.channel.id, "closed")
                
                # Create closed embed
                closed_embed = create_embed(
                    title="Ticket Closed",
                    description=f"This ticket has been closed by {interaction.user.mention}.",
                    color=discord.Color.red().value
                )
                
                # Send closing message
                await interaction.channel.send(embed=closed_embed)
                
                # Revoke permissions for the ticket creator
                if user:
                    try:
                        await interaction.channel.set_permissions(user, overwrite=None)
                    except:
                        pass
                
                # Update channel name to show it's closed
                try:
                    await interaction.channel.edit(name=f"{interaction.channel.name}-closed")
                except discord.Forbidden:
                    pass  # Ignore if we can't rename
                
            elif view.value is False:
                try:
                    await interaction.followup.send("Ticket closure cancelled.", ephemeral=True)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error in handle_close_button: {e}")
            try:
                await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)
            except:
                pass
    
    async def handle_transcript_button(self, interaction: discord.Interaction):
        """Handler for transcript generation button"""
        try:
            # Check if this is a ticket channel
            if not self.is_ticket_channel(interaction.channel.id):
                return await interaction.followup.send(
                    "This button can only be used in a ticket channel.",
                    ephemeral=True
                )
            
            # Check permissions
            if not await self.check_permissions(interaction):
                return await interaction.followup.send(
                    "You don't have permission to generate a transcript.",
                    ephemeral=True
                )
            
            # Skip format selection and generate HTML transcript directly
            await self.generate_transcript_with_format(interaction, interaction.channel.id, "html")
            
        except Exception as e:
            logger.error(f"Error in handle_transcript_button: {e}")
            try:
                await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)
            except:
                pass
    
    async def generate_transcript_with_format(self, interaction: discord.Interaction, channel_id: int, format_type: str = "html"):
        """Generate transcript with HTML format"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            await interaction.followup.send("The ticket channel could not be found.", ephemeral=True)
            return
        
        # Always use HTML format
        format_type = "html"
        
        # Initial response
        await interaction.followup.send(
            "Generating HTML transcript, please wait...",
            ephemeral=False
        )
        
        # Get transcript channel if configured
        transcript_channel_id = config.get("transcript_channel_id")
        transcript_channel = None
        if transcript_channel_id:
            try:
                transcript_channel = interaction.guild.get_channel(int(transcript_channel_id))
            except:
                logger.error(f"Failed to get transcript channel with ID {transcript_channel_id}")
        
        # Check if transcript channel is configured
        if not transcript_channel:
            await interaction.channel.send("No transcript channel is configured. Please ask an admin to set one with `/set_transcript_channel`.")
            return
        
        # Generate transcript
        try:
            transcript_text = await generate_transcript(channel, format_type="html")
            transcript_file_path = await save_transcript(transcript_text, channel.id)
            
            # Create file to send
            if transcript_file_path and os.path.exists(transcript_file_path):
                # Send to transcript channel
                ticket_info = config.get_ticket(channel.id) or {}
                user_id = ticket_info.get("user_id", "Unknown")
                user_mention = f"<@{user_id}>" if user_id != "Unknown" else "Unknown user"
                
                message_content = (
                    f"HTML Transcript for ticket {channel.name} (manual generation)\n"
                    f"Generated by: {interaction.user.mention}\n"
                    f"Ticket creator: {user_mention}\n"
                    f"Format: HTML with enhanced styling"
                )
                
                await transcript_channel.send(
                    message_content,
                    file=discord.File(transcript_file_path)
                )
                
                # Always send a confirmation
                await interaction.channel.send(f"HTML transcript has been sent to {transcript_channel.mention}.")
                
                # Log success
                logger.info(f"HTML transcript generated for channel {channel.id} by {interaction.user.id}")
            else:
                # Send failure message
                await interaction.channel.send("Failed to generate transcript. Please try again.")
                logger.error(f"Failed to generate transcript for channel {channel.id}")
        except Exception as e:
            logger.error(f"Error generating transcript: {e}")
            await interaction.channel.send(f"Error generating transcript: {str(e)[:100]}...")

# Setup function
async def setup(bot):
    ticket_cog = TicketManagement(bot)
    await bot.add_cog(ticket_cog)
    
    # Register persistent views for ticket actions
    try:
        # Create a temporary view for registration purposes
        # This is needed for Discord to recognize and route the interaction
        # to the proper handler when the bot restarts
        temp_view = TicketActionsView(ticket_cog, 0)
        bot.add_view(temp_view)
        logger.info("Registered persistent ticket action views")
    except Exception as e:
        logger.error(f"Error registering persistent views: {e}") 