import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
from typing import Dict, Optional, List, Any, Union
import logging

from config import config
from utils import create_embed, is_valid_url, get_or_create_category, wait_for_message

logger = logging.getLogger(__name__)

# Button for the persistent ticket embed
class TicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Submit Purchase Request",
            emoji="🛒",
            custom_id="persistent_ticket:create"
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Create ticket handler instance and start the flow
        try:
            # Try to defer, but handle the case where it's already been responded to
            is_deferred = False
            try:
                # We'll handle all responses within the ticket handler, just acknowledge here
                await interaction.response.defer(ephemeral=True, thinking=True)
                is_deferred = True
            except discord.errors.HTTPException as e:
                # If the interaction is already acknowledged, we'll handle messages in the handler
                if e.code == 40060:  # Interaction already acknowledged
                    logger.warning(f"Interaction was already acknowledged: {e}")
                    is_deferred = True
                else:
                    # For other HTTP exceptions, re-raise
                    raise
            except Exception as e:
                logger.error(f"Error deferring interaction: {e}")
                is_deferred = False
            
            # Create and start the ticket handler
            handler = TicketCreationHandler(interaction, is_deferred)
            await handler.start_flow()
        except Exception as e:
            logger.error(f"Error in ticket button callback: {e}")
            # Try to send an error message if we haven't responded yet
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred while creating your purchase request. Please try again later.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred while creating your purchase request. Please try again later.", ephemeral=True)
            except Exception:
                pass

# View containing the ticket button for the persistent embed
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view that doesn't timeout
        self.add_item(TicketButton())

# Country selection view
class CountrySelectionView(discord.ui.View):
    def __init__(self, ticket_handler):
        super().__init__(timeout=180)  # 3 minutes timeout
        self.ticket_handler = ticket_handler
        self.value = None
    
    @discord.ui.button(label="Canada", style=discord.ButtonStyle.primary, emoji="🇨🇦", custom_id="country:canada")
    async def canada_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Set the value first
        self.value = "Canada"
        
        # Just acknowledge the interaction without sending any response
        try:
            # Most minimal interaction acknowledgment possible
            await interaction.response.defer(ephemeral=True, thinking=False)
        except discord.errors.InteractionResponded:
            # Interaction was already responded to
            pass
        except Exception as e:
            logger.error(f"Error in Canada button handler: {e}")
            
        # Then stop the view
        self.stop()
    
    @discord.ui.button(label="US", style=discord.ButtonStyle.primary, emoji="🇺🇸", custom_id="country:us")
    async def us_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Set the value first
        self.value = "US"
        
        # Just acknowledge the interaction without sending any response
        try:
            # Most minimal interaction acknowledgment possible
            await interaction.response.defer(ephemeral=True, thinking=False)
        except discord.errors.InteractionResponded:
            # Interaction was already responded to
            pass
        except Exception as e:
            logger.error(f"Error in US button handler: {e}")
            
        # Then stop the view
        self.stop()
    
    async def on_timeout(self):
        self.ticket_handler.timed_out = True

# Group link query view
class GroupLinkView(discord.ui.View):
    def __init__(self, ticket_handler):
        super().__init__(timeout=180)  # 3 minutes timeout
        self.ticket_handler = ticket_handler
        self.value = None
    
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success, emoji="✅", custom_id="group_link:yes")
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        # Only acknowledge the interaction, don't send any response
        try:
            # Use defer instead of sending a response
            await interaction.response.defer(ephemeral=True, thinking=False)
        except:
            pass
        self.stop()
    
    @discord.ui.button(label="No", style=discord.ButtonStyle.danger, emoji="❌", custom_id="group_link:no")
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        # Only acknowledge the interaction, don't send any response
        try:
            # Use defer instead of sending a response
            await interaction.response.defer(ephemeral=True, thinking=False)
        except:
            pass
        self.stop()
    
    async def on_timeout(self):
        self.ticket_handler.timed_out = True

# Payment method selection
class PaymentMethodSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="PayPal", emoji="💰", description="Pay using PayPal"),
            discord.SelectOption(label="Zelle", emoji="💳", description="Pay using Zelle"),
            discord.SelectOption(label="CashApp", emoji="💵", description="Pay using CashApp"),
            discord.SelectOption(label="Other", emoji="🔄", description="Other payment method")
        ]
        super().__init__(
            placeholder="Select a payment method...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="payment_method"
        )
    
    async def callback(self, interaction: discord.Interaction):
        self.view.value = self.values[0]
        # Only acknowledge the interaction, don't send any response
        try:
            # Use defer instead of sending a response
            await interaction.response.defer(ephemeral=True, thinking=False)
        except:
            pass
        self.view.stop()

class PaymentMethodView(discord.ui.View):
    def __init__(self, ticket_handler):
        super().__init__(timeout=180)  # 3 minutes timeout
        self.ticket_handler = ticket_handler
        self.value = None
        self.add_item(PaymentMethodSelect())
    
    async def on_timeout(self):
        self.ticket_handler.timed_out = True

# Ticket creation handler
class TicketCreationHandler:
    def __init__(self, interaction: discord.Interaction, is_deferred=False):
        self.interaction = interaction
        self.bot = interaction.client
        self.user = interaction.user
        self.guild = interaction.guild
        self.data = {}
        self.timed_out = False
        self.ticket_channel = None
        self.ticket_number = 0
        self.is_deferred = is_deferred
        self.ticket_message = None  # Will hold reference to the main ticket message
    
    async def start_flow(self):
        try:
            # Check if the user already has an open ticket
            tickets = config.get("tickets", {})
            for channel_id, ticket_data in tickets.items():
                if int(ticket_data.get("user_id", 0)) == self.user.id and ticket_data.get("status", "") == "open":
                    # User already has an open ticket
                    channel = self.guild.get_channel(int(channel_id))
                    if channel:
                        try:
                            await self.send_response(
                                f"You already have an open ticket in {channel.mention}. Please use that ticket or close it before creating a new one."
                            )
                        except Exception as e:
                            logger.error(f"Error sending response for existing ticket: {e}")
                        return

            # =================================================
            # STEP 1: First, just acknowledge the initial interaction without creating anything yet
            # =================================================
            try:
                # Just acknowledge the button click with a simple loading message
                if not self.interaction.response.is_done():
                    await self.interaction.response.defer(ephemeral=True, thinking=True)
            except Exception as e:
                logger.error(f"Error deferring initial response: {e}")
                return
            
            # =================================================
            # STEP 2: Create the ticket channel
            # =================================================
            success = await self.create_ticket_channel()
            
            # If ticket channel creation failed, stop here
            if not success or not self.ticket_channel:
                await self.interaction.followup.send(
                    "Failed to create a ticket. Please try again later.",
                    ephemeral=True
                )
                return
            
            # =================================================
            # STEP 3: Send a single notification to the user
            # =================================================
            await self.interaction.followup.send(
                f"Your ticket has been created in {self.ticket_channel.mention}",
                ephemeral=True
            )
            
            # =================================================
            # STEP 4: Initialize ticket data
            # =================================================
            self.data["user_id"] = self.user.id
            self.data["username"] = str(self.user)
            self.data["created_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.data["status"] = "open"
            
            # =================================================
            # STEP 5: Start the questionnaire process
            # =================================================
            result = await self.start_ticket_questionnaire()
            
            # If questionnaire failed or timed out, stop here
            if not result:
                return
            
            # =================================================
            # STEP 6: Process the ticket flow
            # =================================================
            try:
                if not self.timed_out:
                    await self.process_ticket_flow()
                    
                    # Update the ticket info at the end if not timed out
                    if not self.timed_out:
                        await self.update_ticket_info()
                else:
                    await self._handle_timeout()
            except Exception as e:
                logger.error(f"Error in ticket flow: {e}")
                if self.ticket_channel:
                    try:
                        error_embed = create_embed(
                            title="Error",
                            description="An error occurred during the ticket creation process. A staff member will assist you shortly.",
                            color=discord.Color.red().value
                        )
                        await self.ticket_channel.send(self.user.mention, embed=error_embed)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Error starting ticket flow: {e}")
            # Try to send a final error message if something went wrong
            try:
                if not self.interaction.response.is_done():
                    await self.interaction.response.send_message("An error occurred creating your ticket. Please try again later.", ephemeral=True)
                else:
                    await self.interaction.followup.send("An error occurred creating your ticket. Please try again later.", ephemeral=True)
            except:
                pass
    
    async def send_response(self, content, **kwargs):
        try:
            # Always ensure ephemeral is set to True if not explicitly specified
            if 'ephemeral' not in kwargs:
                kwargs['ephemeral'] = True
                
            if self.is_deferred:
                await self.interaction.followup.send(content, **kwargs)
            else:
                if not self.interaction.response.is_done():
                    await self.interaction.response.send_message(content, **kwargs)
                else:
                    await self.interaction.followup.send(content, **kwargs)
        except Exception as e:
            logger.error(f"Error sending response: {e}")
    
    async def create_ticket_channel(self):
        try:
            # Get the next ticket number
            latest_ticket = config.get("latest_ticket_number", 0)
            self.ticket_number = latest_ticket + 1
            
            # Get or create the ticket category
            category_name = config.get("ticket_category", "Support Tickets")
            category = await get_or_create_category(self.guild, category_name)
            
            if not category:
                logger.error("Could not get or create ticket category")
                await self.send_response("Error creating ticket: Could not find or create ticket category.")
                return False
            
            # Create the ticket channel
            channel_name = f"ticket-{self.ticket_number:04d}"
            
            # Set permissions
            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                self.guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_messages=True,
                    embed_links=True,
                    attach_files=True,
                    add_reactions=True
                ),
                self.user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    add_reactions=True
                )
            }
            
            # Add permission overwrites for staff roles
            staff_role_ids = config.get("staff_role_ids", [])
            for role_id in staff_role_ids:
                role = self.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_channels=True,
                        manage_messages=True,
                        embed_links=True,
                        attach_files=True,
                        add_reactions=True
                    )
            
            # Create the channel
            self.ticket_channel = await self.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Support ticket for {self.user}"
            )
            
            # Update the latest ticket number
            config.set("latest_ticket_number", self.ticket_number)
            
            return True
        except Exception as e:
            logger.error(f"Error creating ticket channel: {e}")
            await self.send_response("Error creating ticket channel. Please try again later.")
            return False
    
    async def start_ticket_questionnaire(self):
        """Create the initial ticket message with welcome and first step (country selection)"""
        welcome_embed = create_embed(
            title=f"Purchase Request #{self.ticket_number:04d} - Setup",
            description=f"Welcome {self.user.mention}!\n\nPlease complete the following steps to submit your purchase request.",
            color=discord.Color.blue().value,
            fields=[
                {"name": "Step 1: Select Your Country", "value": "Please select your country from the options below.", "inline": False}
            ]
        )
        
        view = CountrySelectionView(self)
        self.ticket_message = await self.ticket_channel.send(embed=welcome_embed, view=view)
        
        # Wait for country selection
        await view.wait()
        
        if view.value:
            self.data["country"] = view.value
            return True
        else:
            self.timed_out = True
            return False
    
    async def process_ticket_flow(self):
        """Process the entire ticket flow using a single message that gets updated"""
        # We've already done country selection in start_ticket_questionnaire
        if self.timed_out:
            return
        
        # Step 2: Group Link
        group_link_embed = create_embed(
            title=f"Purchase Request #{self.ticket_number:04d} - Setup",
            description=f"Welcome {self.user.mention}!",
            color=discord.Color.blue().value,
            fields=[
                {"name": "Step 1: Country ✅", "value": f"Selected: **{self.data['country']}**", "inline": False},
                {"name": "Step 2: Group Link", "value": "Do you have a group link to share with us?", "inline": False}
            ]
        )
        
        group_link_view = GroupLinkView(self)
        await self.ticket_message.edit(embed=group_link_embed, view=group_link_view)
        
        # Wait for group link selection
        await group_link_view.wait()
        
        if self.timed_out:
            return
            
        # Handle group link response
        if group_link_view.value:
            self.data["has_group_link"] = True
            
            # Update the message to prompt for the group link
            prompt_embed = create_embed(
                title=f"Purchase Request #{self.ticket_number:04d} - Setup",
                description=f"Welcome {self.user.mention}!",
                color=discord.Color.blue().value,
                fields=[
                    {"name": "Step 1: Country ✅", "value": f"Selected: **{self.data['country']}**", "inline": False},
                    {"name": "Step 2: Group Link ✅", "value": "Please type your group link in the chat.", "inline": False}
                ]
            )
            
            # Send message prompting for the link
            await self.ticket_message.edit(embed=prompt_embed, view=None)
            
            # Wait for the user to type the link
            try:
                message = await wait_for_message(self.bot, self.user, self.ticket_channel, timeout=180)
                
                if message:
                    self.data["group_link"] = message.content
                    
                    # Try to delete the user's message to keep the channel clean
                    try:
                        await message.delete()
                    except:
                        pass
                    
                    # Update the message with the provided link
                    link_provided_embed = create_embed(
                        title=f"Purchase Request #{self.ticket_number:04d} - Setup",
                        description=f"Welcome {self.user.mention}!",
                        color=discord.Color.blue().value,
                        fields=[
                            {"name": "Step 1: Country ✅", "value": f"Selected: **{self.data['country']}**", "inline": False},
                            {"name": "Step 2: Group Link ✅", "value": f"Link provided: **{message.content}**", "inline": False},
                            {"name": "Step 3: Payment Method", "value": "Please select your preferred payment method:", "inline": False}
                        ]
                    )
                    
                    # Move to payment method selection
                    payment_view = PaymentMethodView(self)
                    await self.ticket_message.edit(embed=link_provided_embed, view=payment_view)
                    
                    # Wait for payment method selection
                    await payment_view.wait()
                    
                    if payment_view.value:
                        self.data["payment_method"] = payment_view.value
                        
                        # Temporary completion message - will be replaced by update_ticket_info
                        completion_embed = create_embed(
                            title=f"Purchase Request #{self.ticket_number:04d} - Setup Complete",
                            description=f"Thank you {self.user.mention}! Processing your information...",
                            color=discord.Color.green().value,
                            fields=[
                                {"name": "Step 1: Country ✅", "value": f"Selected: **{self.data['country']}**", "inline": False},
                                {"name": "Step 2: Group Link ✅", "value": f"Link provided: **{message.content}**", "inline": False},
                                {"name": "Step 3: Payment Method ✅", "value": f"Selected: **{payment_view.value}**", "inline": False}
                            ]
                        )
                        
                        # Show a temporary message while we prepare the final summary
                        await self.ticket_message.edit(embed=completion_embed, view=None)
                        # Don't end the flow here - update_ticket_info will provide the final message
                    else:
                        self.timed_out = True
                else:
                    self.timed_out = True
            except asyncio.TimeoutError:
                self.timed_out = True
        else:
            # User doesn't have a group link
            self.data["has_group_link"] = False
            self.data["group_link"] = "No link provided"
            
            # Update the message to show no group link and ask for payment method
            no_link_embed = create_embed(
                title=f"Purchase Request #{self.ticket_number:04d} - Setup",
                description=f"Welcome {self.user.mention}!",
                color=discord.Color.blue().value,
                fields=[
                    {"name": "Step 1: Country ✅", "value": f"Selected: **{self.data['country']}**", "inline": False},
                    {"name": "Step 2: Group Link ✅", "value": "No link provided", "inline": False},
                    {"name": "Step 3: Payment Method", "value": "Please select your preferred payment method:", "inline": False}
                ]
            )
            
            # Move to payment method selection
            payment_view = PaymentMethodView(self)
            await self.ticket_message.edit(embed=no_link_embed, view=payment_view)
            
            # Wait for payment method selection
            await payment_view.wait()
            
            if payment_view.value:
                self.data["payment_method"] = payment_view.value
                
                # Temporary completion message - will be replaced by update_ticket_info
                completion_embed = create_embed(
                    title=f"Purchase Request #{self.ticket_number:04d} - Setup Complete",
                    description=f"Thank you {self.user.mention}! Processing your information...",
                    color=discord.Color.green().value,
                    fields=[
                        {"name": "Step 1: Country ✅", "value": f"Selected: **{self.data['country']}**", "inline": False},
                        {"name": "Step 2: Group Link ✅", "value": "No link provided", "inline": False},
                        {"name": "Step 3: Payment Method ✅", "value": f"Selected: **{payment_view.value}**", "inline": False}
                    ]
                )
                
                # Show a temporary message while we prepare the final summary
                await self.ticket_message.edit(embed=completion_embed, view=None)
                # Don't end the flow here - update_ticket_info will provide the final message
            else:
                self.timed_out = True
    
    async def update_ticket_info(self):
        # Create the ticket information summary embed with the new format
        country = self.data.get("country", "Not specified")
        group_link = self.data.get("group_link", "No link provided")
        payment_method = self.data.get("payment_method", "Not specified")
        
        # Format the description with code blocks for each piece of information
        description = (
            f"**COUNTRY**\n```\n{country}\n```\n"
            f"**GROUP LINK**\n```\n{group_link}\n```\n"
            f"**PAYMENT METHOD**\n```\n{payment_method}\n```\n"
            f"-# If you have **any** special delivery instructions or live in an apartment please let \n"
            f"-# staff know _before the order is placed_"
        )
        
        embed = create_embed(
            title="Purchase Request",
            description=description,
            color=discord.Color.from_rgb(46, 204, 113).value  # Green color
        )
        
        # Update the existing ticket message with the summary info
        await self.ticket_message.edit(embed=embed, view=None)
        
        # Ping any staff roles in a separate message
        staff_ping = ""
        staff_role_ids = config.get("staff_role_ids", [])
        for role_id in staff_role_ids:
            role = self.guild.get_role(role_id)
            if role:
                staff_ping += f"{role.mention} "
        
        # Send a separate notification to staff
        if staff_ping:
            staff_notification = create_embed(
                title=f"New Purchase Request",
                description=f"A new purchase request has been submitted and is ready for processing.",
                color=discord.Color.gold().value,
                fields=[
                    {"name": "Ticket", "value": f"#{self.ticket_number:04d}", "inline": True},
                    {"name": "User", "value": self.user.mention, "inline": True}
                ]
            )
            await self.ticket_channel.send(staff_ping, embed=staff_notification)
        
        # Update the ticket data in config
        config.add_ticket(
            channel_id=self.ticket_channel.id,
            user_id=self.user.id,
            data=self.data
        )
    
    async def _handle_timeout(self):
        if self.ticket_channel:
            timeout_embed = create_embed(
                title="Purchase Request Setup Timed Out",
                description="The purchase request setup process has timed out. A staff member will assist you shortly.",
                color=discord.Color.red().value
            )
            await self.ticket_channel.send(self.user.mention, embed=timeout_embed)

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persistent_views_added = False
        self.cooldowns = {}
    
    # This runs when the cog is loaded
    async def cog_load(self):
        # Add our persistent view if it wasn't already added
        if not self.persistent_views_added:
            self.bot.add_view(TicketView())
            self.persistent_views_added = True
    
    # Check if user is on cooldown for ticket creation
    def is_on_cooldown(self, user_id):
        if user_id in self.cooldowns:
            # Check if cooldown has expired
            if datetime.datetime.now() < self.cooldowns[user_id]:
                return True
            else:
                # Cooldown expired, remove it
                del self.cooldowns[user_id]
        return False
    
    # Add user to cooldown
    def add_cooldown(self, user_id, seconds=30):
        self.cooldowns[user_id] = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
    
    @app_commands.command(name="setup_ticket", description="Set up the purchase request system")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.guild_id)  # 1 use per 60 seconds per guild
    async def setup_ticket(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        try:
            # Use the specified channel or the current one
            target_channel = channel or interaction.channel
            
            # Create the embed for the ticket system
            embed = create_embed(
                title="Purchase Request System",
                description="Click the button below to submit a new purchase request.",
                color=discord.Color.blue().value,
                footer_text="Purchase requests are used to order food/items from supported services."
            )
            
            # Send the embed with the view
            view = TicketView()
            message = await target_channel.send(embed=embed, view=view)
            
            # Store the message and channel ID for persistence
            config.set("ticket_embed_message_id", message.id)
            config.set("ticket_embed_channel_id", target_channel.id)
            
            # Acknowledge the interaction if not already done
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Purchase request system set up in {target_channel.mention}!", ephemeral=True)
                else:
                    await interaction.followup.send(f"Purchase request system set up in {target_channel.mention}!", ephemeral=True)
            except discord.errors.HTTPException as e:
                if e.code != 40060:  # Ignore "already acknowledged" errors
                    raise
            except Exception as e:
                logger.error(f"Error in setup_ticket command: {e}")
        except Exception as e:
            logger.error(f"Error setting up purchase request system: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred while setting up the purchase request system.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred while setting up the purchase request system.", ephemeral=True)
            except:
                pass
    
    @commands.Cog.listener()
    async def on_ready(self):
        # Add the persistent view when the bot starts
        if not self.persistent_views_added:
            self.bot.add_view(TicketView())
            self.persistent_views_added = True

# Setup function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(Tickets(bot)) 