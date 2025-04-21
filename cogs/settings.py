import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
from typing import Dict, List, Optional, Any

from config import config
from utils import create_embed

logger = logging.getLogger(__name__)

# Main Settings View with buttons for different configuration sections
class SettingsView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=180)  # 3 minute timeout
        self.cog = cog
    
    @discord.ui.button(label="Config", style=discord.ButtonStyle.secondary, emoji="<:ticket_configuration:1363768515664019486>", row=0)
    async def bot_config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_bot_config_category(interaction)
    
    @discord.ui.button(label="Staff", style=discord.ButtonStyle.secondary, emoji="<:ticket_staff:1363764012776685638>", row=0)
    async def staff_settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_staff_category(interaction)
    
    @discord.ui.button(label="Templates", style=discord.ButtonStyle.secondary, emoji="<:ticket_embed:1363763988399394968>", row=0)
    async def message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_message_settings(interaction)

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.value = None
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()

# Staff Role management view
class StaffRoleView(discord.ui.View):
    def __init__(self, cog, roles, current_staff_roles):
        super().__init__(timeout=180)
        self.cog = cog
        self.add_item(StaffRoleSelect(roles, current_staff_roles))
    
    @discord.ui.button(label="Back to Staff", style=discord.ButtonStyle.secondary, emoji="<:undo:1362583079692140594>")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Return to Staff Category view instead of main settings
        await self.cog.show_staff_category(interaction)

class StaffRoleSelect(discord.ui.Select):
    def __init__(self, roles, current_staff_roles):
        # Convert current staff roles from IDs to int for comparison
        current_staff_role_ids = [int(role_id) for role_id in current_staff_roles]
        
        # Create options from server roles, marking current staff roles as default
        options = [
            discord.SelectOption(
                label=role.name,
                value=str(role.id),
                default=role.id in current_staff_role_ids
            ) for role in roles[:25]  # Discord limits to 25 options
        ]
        
        super().__init__(
            placeholder="Select staff roles...",
            min_values=0,
            max_values=len(options),
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Update staff roles in config
        config.set("staff_role_ids", [int(role_id) for role_id in self.values])
        config.save()  # Save immediately
        
        # Show the updated roles
        roles = interaction.guild.roles
        current_staff_roles = config.get("staff_role_ids", [])
        
        # Create embed
        embed = create_embed(
            title="Staff Role Configuration",
            description="Select which roles should have staff permissions in tickets.",
            color=discord.Color(0x5701c5)
        )
        
        # List current staff roles
        if current_staff_roles:
            role_mentions = []
            for role_id in current_staff_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(f"<@&{role.id}>")
            
            embed.add_field(
                name="Current Staff Roles",
                value=", ".join(role_mentions) if role_mentions else "No roles configured",
                inline=False
            )
        else:
            embed.add_field(
                name="Current Staff Roles",
                value="No roles configured",
                inline=False
            )
            
        # Notification about update
        embed.add_field(
            name="Success",
            value=f"Updated staff roles! Selected {len(self.values)} roles.",
            inline=False
        )
        
        await interaction.response.edit_message(
            embed=embed,
            view=StaffRoleView(interaction.client.get_cog("Settings"), roles, current_staff_roles)
        )

# Channel configuration view
class ChannelConfigView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=180)
        self.cog = cog
    
    @discord.ui.button(label="Channel", style=discord.ButtonStyle.primary, row=0)
    async def ticket_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Send a modal to get channel ID
        modal = ChannelSelectModal(title="Set Ticket Channel", custom_id="ticket_channel")
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.channel_id:
            config.set("ticket_channel_id", modal.channel_id)
            config.save()  # Save immediately
            await self.cog.show_channel_settings(interaction, f"Ticket channel set to <#{modal.channel_id}>")
        else:
            await self.cog.show_channel_settings(interaction)
    
    @discord.ui.button(label="Set Category", style=discord.ButtonStyle.primary, row=0)
    async def category_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Send a modal to get category ID
        modal = ChannelSelectModal(title="Category", custom_id="ticket_category")
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.channel_id:
            config.set("ticket_category_id", modal.channel_id)
            config.save()  # Save immediately
            await self.cog.show_channel_settings(interaction, f"Ticket category set to <#{modal.channel_id}>")
        else:
            await self.cog.show_channel_settings(interaction)
    
    @discord.ui.button(label="Transcripts", style=discord.ButtonStyle.primary, row=1)
    async def transcript_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Send a modal to get channel ID
        modal = ChannelSelectModal(title="Set Transcript Channel", custom_id="transcript_channel")
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.channel_id:
            config.set("transcript_channel_id", modal.channel_id)
            config.save()  # Save immediately
            await self.cog.show_channel_settings(interaction, f"Transcript channel set to <#{modal.channel_id}>")
        else:
            await self.cog.show_channel_settings(interaction)
    
    @discord.ui.button(label="Back to Config", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Return to Bot Config Category view instead of main settings
        await self.cog.show_bot_config_category(interaction)

class ChannelSelectModal(discord.ui.Modal):
    def __init__(self, title, custom_id):
        super().__init__(title=title)
        self.channel_id = None
        
        self.channel_input = discord.ui.TextInput(
            label="Enter Channel ID or #mention",
            placeholder="Enter the channel ID or mention (#channel)",
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel_input = self.channel_input.value.strip()
        
        # Check if it's a mention
        if channel_input.startswith('<#') and channel_input.endswith('>'):
            channel_id = int(channel_input[2:-1])
        else:
            # Try to convert to int
            try:
                channel_id = int(channel_input)
            except ValueError:
                await interaction.response.send_message("Invalid channel ID. Please provide a valid channel ID or mention.", ephemeral=True)
                self.stop()
                return
        
        # Verify channel exists
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("Channel not found. Please provide a valid channel ID.", ephemeral=True)
            self.stop()
            return
        
        self.channel_id = channel_id
        await interaction.response.defer()
        self.stop()

# Cooldown settings view with slider-like buttons
class CooldownView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=180)
        self.cog = cog
        self.cooldown = config.get("ticket_cooldown", 30)  # Default 30 seconds
    
    @discord.ui.button(label="➖ 10", style=discord.ButtonStyle.secondary, row=0)
    async def decrease10_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cooldown = max(0, self.cooldown - 10)
        config.set("ticket_cooldown", self.cooldown)
        config.save()  # Save immediately
        await self.cog.show_cooldown_settings(interaction)
    
    @discord.ui.button(label="➖ 5", style=discord.ButtonStyle.secondary, row=0)
    async def decrease5_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cooldown = max(0, self.cooldown - 5)
        config.set("ticket_cooldown", self.cooldown)
        config.save()  # Save immediately
        await self.cog.show_cooldown_settings(interaction)
    
    @discord.ui.button(label="➕ 5", style=discord.ButtonStyle.secondary, row=0)
    async def increase5_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cooldown = self.cooldown + 5
        config.set("ticket_cooldown", self.cooldown)
        config.save()  # Save immediately
        await self.cog.show_cooldown_settings(interaction)
    
    @discord.ui.button(label="➕ 10", style=discord.ButtonStyle.secondary, row=0)
    async def increase10_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cooldown = self.cooldown + 10
        config.set("ticket_cooldown", self.cooldown)
        config.save()  # Save immediately
        await self.cog.show_cooldown_settings(interaction)
    
    @discord.ui.button(label="Back to Staff", style=discord.ButtonStyle.secondary, emoji="<:undo:1362583079692140594>", row=0)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Return to Staff Category view instead of main settings
        await self.cog.show_staff_category(interaction)

# Category views for hierarchical navigation
class BotConfigCategoryView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=180)
        self.cog = cog
    
    @discord.ui.button(label="Channel", style=discord.ButtonStyle.secondary, emoji="<:ticket_channel:1363764000822792395>", row=0)
    async def ticket_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_ticket_channel_settings(interaction)
    
    @discord.ui.button(label="Category", style=discord.ButtonStyle.secondary, emoji="<:ticket_configuration:1363768515664019486>", row=0)
    async def ticket_category_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_ticket_category_settings(interaction)
    
    @discord.ui.button(label="Transcripts", style=discord.ButtonStyle.secondary, emoji="<:ticket_transcription:1363769297331028049>", row=0)
    async def transcript_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_transcript_channel_settings(interaction)
    
    @discord.ui.button(label="Main Menu", style=discord.ButtonStyle.secondary, emoji="<:undo:1362583079692140594>", row=0)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.cog._create_settings_overview_embed()
        await interaction.response.edit_message(embed=embed, view=SettingsView(self.cog))

class StaffCategoryView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=180)
        self.cog = cog
    
    @discord.ui.button(label="Roles", style=discord.ButtonStyle.secondary, emoji="<:ticket_staff:1363764012776685638>", row=0)
    async def staff_roles_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_staff_roles_settings(interaction)
    
    @discord.ui.button(label="Cooldowns", style=discord.ButtonStyle.secondary, emoji="<:ticket_cooldown:1363764006711595049>", row=0)
    async def cooldown_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_cooldown_settings(interaction)
    
    @discord.ui.button(label="Main Menu", style=discord.ButtonStyle.secondary, emoji="<:undo:1362583079692140594>", row=0)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.cog._create_settings_overview_embed()
        await interaction.response.edit_message(embed=embed, view=SettingsView(self.cog))

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def _create_settings_overview_embed(self):
        """Helper function to create the settings overview embed consistently"""
        embed = create_embed(
            title=None,  # Remove title as we'll use author field instead
            description=(
                "Manage your bot settings and user experience from the options below\n"
                "-# ╰・your settings are automatically saved\n\n"
                "**BOT CONFIGURATION** ↴\n"
                "<:ticket_channel:1363764000822792395> *Ticket Channel (required)*: Where users create tickets\n"
                "<:ticket_configuration:1363768515664019486> *Ticket Category (required):*  Where tickets are organized\n"
                "<:ticket_transcription:1363769297331028049> *Transcript Channel (required)*: Where ticket transcripts are sent\n\n"
                "**STAFF SETTINGS** ↴\n"
                "<:ticket_staff:1363764012776685638> *Staff Roles (required)*: Roles that can manage tickets\n"
                "<:ticket_cooldown:1363764006711595049> *Ticket Cooldown (default: 30s)*: Time between ticket creation\n\n"
                "**MESSAGE TEMPLATES** ↴\n"
                "<:ticket_embed:1363763988399394968> *Custom Messages (optional)*: Modify bot responses\n\n"
                "-# Settings should be configured **before** allowing users to create tickets"
            ),
            color=discord.Color(0x5701c5)  # Convert hexadecimal to decimal: 5702085
        )
        
        # Set the author field
        embed.set_author(
            name="User Settings (overview)",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        return embed
    
    @app_commands.command(name="settings", description="Configure ticket bot settings")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        """Shows the settings panel for the ticket bot"""
        await self.show_settings(interaction)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display the main settings embed with options"""
        # Create settings embed using helper method
        embed = self._create_settings_overview_embed()
        
        # Send or edit settings embed with view
        view = SettingsView(self)
        
        try:
            # Always try to edit the original message if possible
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                # Try to use edit_original_response first
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception:
                    # If the original message can't be edited (e.g., different interaction),
                    # try to edit the message from the interaction
                    try:
                        await interaction.response.edit_message(embed=embed, view=view)
                    except Exception:
                        # If all fails, just send a new message
                        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error updating settings message: {e}")
            # Last resort fallback
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def show_bot_config_category(self, interaction: discord.Interaction):
        """Show Bot Configuration category options"""
        embed = create_embed(
            title=None,
            description="Select which aspect of the bot you want to configure.",
            color=discord.Color(0x5701c5)
        )
        
        embed.set_author(
            name="Bot Config (settings)",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        ticket_channel_id = config.get("ticket_channel_id")
        ticket_category_id = config.get("ticket_category_id")
        transcript_channel_id = config.get("transcript_channel_id")
        
        embed.add_field(
            name=f"<:ticket_channel:1363764000822792395> Ticket Channel: {f'<#{ticket_channel_id}>' if ticket_channel_id else '*Not set*'}",
            value="-# ╰・This is where users will see the ticket creation button.",
            inline=False
        )
        
        embed.add_field(
            name=f"<:ticket_configuration:1363768515664019486> Ticket Category: {f'<#{ticket_category_id}>' if ticket_category_id else '*Not set*'}",
            value="-# ╰・All created tickets will be placed in this category.",
            inline=False
        )
        
        embed.add_field(
            name=f"<:ticket_transcription:1363769297331028049> Transcript Channel: {f'<#{transcript_channel_id}>' if transcript_channel_id else '*Not set*'}",
            value="-# ╰・When tickets are closed, transcripts will be sent to this channel.",
            inline=False
        )
        
        try:
            await interaction.response.edit_message(embed=embed, view=BotConfigCategoryView(self))
        except Exception as e:
            logger.error(f"Error showing bot config category: {e}")
            await interaction.followup.send(embed=embed, view=BotConfigCategoryView(self), ephemeral=True)

    async def show_staff_category(self, interaction: discord.Interaction):
        """Show Staff Settings category options"""
        embed = create_embed(
            title=None,
            description="Select which staff-related settings you want to configure.",
            color=discord.Color(0x5701c5)
        )
        
        embed.set_author(
            name="STAFF SETTINGS",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        # Staff roles summary
        staff_roles = config.get('staff_role_ids', [])
        role_count = len(staff_roles)
        
        embed.add_field(
            name=f"<:ticket_staff:1363764012776685638> Staff Roles: {role_count} role(s)",
            value="-# ╰・Roles that have permission to manage and respond to tickets.",
            inline=False
        )
        
        # Cooldown summary
        cooldown = config.get("ticket_cooldown", 30)
        
        embed.add_field(
            name=f"<:ticket_cooldown:1363764006711595049> Ticket Cooldown: {cooldown} seconds",
            value="-# ╰・Time users must wait between creating tickets.",
            inline=False
        )
        
        try:
            await interaction.response.edit_message(embed=embed, view=StaffCategoryView(self))
        except Exception as e:
            logger.error(f"Error showing staff category: {e}")
            await interaction.followup.send(embed=embed, view=StaffCategoryView(self), ephemeral=True)
    
    async def show_staff_roles_settings(self, interaction: discord.Interaction):
        """Show staff role configuration"""
        # Get all server roles and current staff roles
        roles = interaction.guild.roles
        current_staff_roles = config.get("staff_role_ids", [])
        
        # Create embed
        embed = create_embed(
            title=None,
            description="Configure staff roles that can manage tickets and help users.",
            color=discord.Color(0x5701c5)
        )
        
        embed.set_author(
            name="STAFF ROLES SETTINGS",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        # List current staff roles
        if current_staff_roles:
            role_mentions = []
            for role_id in current_staff_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(f"<@&{role.id}>")
            
            role_text = ", ".join(role_mentions) if role_mentions else "No roles configured"
            embed.add_field(
                name=f"<:ticket_staff:1363764012776685638> Current Staff Roles: {role_text}",
                value="-# ╰・These roles can manage and respond to tickets.",
                inline=False
            )
        else:
            embed.add_field(
                name="<:ticket_staff:1363764012776685638> Current Staff Roles: No roles configured",
                value="-# ╰・Select roles below to give them staff permissions.",
                inline=False
            )
        
        embed.add_field(
            name="Instructions",
            value="Select which roles should have staff permissions to manage tickets. Staff members can view, close, and manage all tickets.",
            inline=False
        )
        
        # Update the existing message
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=StaffRoleView(self, roles, current_staff_roles))
            else:
                try:
                    await interaction.edit_original_response(embed=embed, view=StaffRoleView(self, roles, current_staff_roles))
                except Exception:
                    await interaction.followup.send(embed=embed, view=StaffRoleView(self, roles, current_staff_roles), ephemeral=True)
        except Exception as e:
            logger.error(f"Error updating staff roles view: {e}")
            await interaction.followup.send(embed=embed, view=StaffRoleView(self, roles, current_staff_roles), ephemeral=True)
    
    async def show_channel_settings(self, interaction: discord.Interaction, success_message=None):
        """Show channel configuration settings"""
        # Get current channel settings
        ticket_channel_id = config.get("ticket_channel_id")
        ticket_category_id = config.get("ticket_category_id")
        transcript_channel_id = config.get("transcript_channel_id")
        
        # Create embed
        embed = create_embed(
            title="BOT CONFIGURATION",
            description="Configure the channels used by the ticket system.",
            color=discord.Color(0x5701c5)
        )
        
        # Add current settings
        embed.add_field(
            name="🎟️ Ticket Channel *(required)*",
            value=f"Current: {f'<#{ticket_channel_id}>' if ticket_channel_id else 'Not set'}\nWhere users create tickets",
            inline=False
        )
        
        embed.add_field(
            name="📁 Ticket Category *(required)*",
            value=f"Current: {f'<#{ticket_category_id}>' if ticket_category_id else 'Not set'}\nWhere tickets are organized",
            inline=False
        )
        
        embed.add_field(
            name="📝 Transcript Channel *(optional)*",
            value=f"Current: {f'<#{transcript_channel_id}>' if transcript_channel_id else 'Not set'}\nWhere ticket transcripts are sent",
            inline=False
        )
        
        # Add success message if provided
        if success_message:
            embed.add_field(
                name="Success",
                value=success_message,
                inline=False
            )
        
        # Update the existing message
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=ChannelConfigView(self))
            else:
                try:
                    await interaction.edit_original_response(embed=embed, view=ChannelConfigView(self))
                except Exception:
                    await interaction.followup.send(embed=embed, view=ChannelConfigView(self), ephemeral=True)
        except Exception as e:
            logger.error(f"Error updating channel settings view: {e}")
            await interaction.followup.send(embed=embed, view=ChannelConfigView(self), ephemeral=True)
    
    async def show_message_settings(self, interaction: discord.Interaction):
        """Show message template settings"""
        # This would be implemented similarly to the other settings pages
        # For now, just show a placeholder
        embed = create_embed(
            title=None,
            description="Configure custom message templates for tickets.",
            color=discord.Color(0x5701c5)
        )
        
        embed.set_author(
            name="MESSAGE TEMPLATES",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        embed.add_field(
            name="<:ticket_embed:1363763988399394968> Custom Messages *(coming soon)*: Not available",
            value="-# ╰・Customize the messages sent by the bot for various actions.",
            inline=False
        )
        
        # Simple view with buttons in row 0
        view = discord.ui.View()
        back_button = discord.ui.Button(label="Main Menu", style=discord.ButtonStyle.secondary, custom_id="back", row=0, emoji="<:undo:1362583079692140594>")
        
        async def back_button_callback(back_interaction: discord.Interaction):
            # Get the settings embed from the helper method
            settings_embed = self._create_settings_overview_embed()
            
            # Update directly using this interaction
            await back_interaction.response.edit_message(embed=settings_embed, view=SettingsView(self))
        
        back_button.callback = back_button_callback
        view.add_item(back_button)
        
        # Update the existing message
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception:
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error updating message settings view: {e}")
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def show_cooldown_settings(self, interaction: discord.Interaction):
        """Show cooldown configuration"""
        cooldown = config.get("ticket_cooldown", 30)
        
        # Create embed for consistency
        embed = create_embed(
            title=None,
            description="Configure how long users must wait between creating tickets.",
            color=discord.Color(0x5701c5)
        )
        
        embed.set_author(
            name="COOLDOWN SETTINGS",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        embed.add_field(
            name=f"<:ticket_cooldown:1363764006711595049> Ticket Cooldown: **{cooldown} seconds**",
            value="-# ╰・Use the buttons below to adjust the cooldown period.",
            inline=False
        )
        
        # Update the existing message
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=CooldownView(self))
            else:
                try:
                    await interaction.edit_original_response(embed=embed, view=CooldownView(self))
                except Exception:
                    await interaction.followup.send(embed=embed, view=CooldownView(self), ephemeral=True)
        except Exception as e:
            logger.error(f"Error updating cooldown settings view: {e}")
            await interaction.followup.send(embed=embed, view=CooldownView(self), ephemeral=True)

    async def show_ticket_channel_settings(self, interaction: discord.Interaction, success_message=None):
        """Show ticket channel settings"""
        ticket_channel_id = config.get("ticket_channel_id")
        
        embed = create_embed(
            title=None,
            description="Configure the channel where users can create tickets.",
            color=discord.Color(0x5701c5)
        )
        
        embed.set_author(
            name="TICKET CHANNEL SETTINGS",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        embed.add_field(
            name=f"<:ticket_channel:1363764000822792395> Current Ticket Channel: {f'<#{ticket_channel_id}>' if ticket_channel_id else '*Not set*'}",
            value="-# ╰・This is where users will see the ticket creation button.",
            inline=False
        )
        
        # Add success message if provided
        if success_message:
            embed.add_field(
                name="Success",
                value=success_message,
                inline=False
            )
        
        # Create a modal for setting the ticket channel
        class TicketChannelView(discord.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=180)
                self.cog = cog
            
            @discord.ui.button(label="Set Ticket Channel", style=discord.ButtonStyle.primary, emoji="<:ticket_channel:1363764000822792395>", row=0)
            async def set_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                modal = ChannelSelectModal(title="Set Ticket Channel", custom_id="ticket_channel")
                await button_interaction.response.send_modal(modal)
                await modal.wait()
                
                if modal.channel_id:
                    config.set("ticket_channel_id", modal.channel_id)
                    config.save()  # Save immediately
                    await self.cog.show_ticket_channel_settings(button_interaction, f"Ticket channel set to <#{modal.channel_id}>")
                else:
                    await self.cog.show_ticket_channel_settings(button_interaction)
            
            @discord.ui.button(label="Back to Config", style=discord.ButtonStyle.secondary, emoji="<:undo:1362583079692140594>", row=0)
            async def back_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                await self.cog.show_bot_config_category(button_interaction)
        
        try:
            await interaction.response.edit_message(embed=embed, view=TicketChannelView(self))
        except Exception as e:
            logger.error(f"Error showing ticket channel settings: {e}")
            await interaction.followup.send(embed=embed, view=TicketChannelView(self), ephemeral=True)

    async def show_ticket_category_settings(self, interaction: discord.Interaction, success_message=None):
        """Show ticket category settings"""
        ticket_category_id = config.get("ticket_category_id")
        
        embed = create_embed(
            title=None,
            description="Configure the category where tickets will be organized.",
            color=discord.Color(0x5701c5)
        )
        
        embed.set_author(
            name="TICKET CATEGORY SETTINGS",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        embed.add_field(
            name=f"<:ticket_configuration:1363768515664019486> Current Ticket Category: {f'<#{ticket_category_id}>' if ticket_category_id else '*Not set*'}",
            value="-# ╰・All created tickets will be placed in this category.",
            inline=False
        )
        
        # Add success message if provided
        if success_message:
            embed.add_field(
                name="Success",
                value=success_message,
                inline=False
            )
        
        # Create a modal for setting the ticket category
        class TicketCategoryView(discord.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=180)
                self.cog = cog
            
            @discord.ui.button(label="Set Ticket Category", style=discord.ButtonStyle.primary, emoji="<:ticket_configuration:1363768515664019486>", row=0)
            async def set_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                modal = ChannelSelectModal(title="Set Ticket Category", custom_id="ticket_category")
                await button_interaction.response.send_modal(modal)
                await modal.wait()
                
                if modal.channel_id:
                    config.set("ticket_category_id", modal.channel_id)
                    config.save()  # Save immediately
                    await self.cog.show_ticket_category_settings(button_interaction, f"Ticket category set to <#{modal.channel_id}>")
                else:
                    await self.cog.show_ticket_category_settings(button_interaction)
            
            @discord.ui.button(label="Back to Config", style=discord.ButtonStyle.secondary, emoji="<:undo:1362583079692140594>", row=0)
            async def back_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                await self.cog.show_bot_config_category(button_interaction)
        
        try:
            await interaction.response.edit_message(embed=embed, view=TicketCategoryView(self))
        except Exception as e:
            logger.error(f"Error showing ticket category settings: {e}")
            await interaction.followup.send(embed=embed, view=TicketCategoryView(self), ephemeral=True)

    async def show_transcript_channel_settings(self, interaction: discord.Interaction, success_message=None):
        """Show transcript channel settings"""
        transcript_channel_id = config.get("transcript_channel_id")
        
        embed = create_embed(
            title=None,
            description="Configure the channel where ticket transcripts will be sent.",
            color=discord.Color(0x5701c5)
        )
        
        embed.set_author(
            name="TRANSCRIPT CHANNEL SETTINGS",
            icon_url="https://i.gyazo.com/97be0efe0b5f5dc42afc223b0fcd908a.png"
        )
        
        embed.add_field(
            name=f"<:ticket_transcription:1363769297331028049> Current Transcript Channel: {f'<#{transcript_channel_id}>' if transcript_channel_id else '*Not set*'}",
            value="-# ╰・When tickets are closed, transcripts will be sent to this channel.",
            inline=False
        )
        
        # Add success message if provided
        if success_message:
            embed.add_field(
                name="Success",
                value=success_message,
                inline=False
            )
        
        # Create a modal for setting the transcript channel
        class TranscriptChannelView(discord.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=180)
                self.cog = cog
            
            @discord.ui.button(label="Set Transcript Channel", style=discord.ButtonStyle.primary, emoji="<:ticket_transcription:1363769297331028049>", row=0)
            async def set_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                modal = ChannelSelectModal(title="Set Transcript Channel", custom_id="transcript_channel")
                await button_interaction.response.send_modal(modal)
                await modal.wait()
                
                if modal.channel_id:
                    config.set("transcript_channel_id", modal.channel_id)
                    config.save()  # Save immediately
                    await self.cog.show_transcript_channel_settings(button_interaction, f"Transcript channel set to <#{modal.channel_id}>")
                else:
                    await self.cog.show_transcript_channel_settings(button_interaction)
            
            @discord.ui.button(label="Back to Config", style=discord.ButtonStyle.secondary, emoji="<:undo:1362583079692140594>", row=0)
            async def back_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                await self.cog.show_bot_config_category(button_interaction)
        
        try:
            await interaction.response.edit_message(embed=embed, view=TranscriptChannelView(self))
        except Exception as e:
            logger.error(f"Error showing transcript channel settings: {e}")
            await interaction.followup.send(embed=embed, view=TranscriptChannelView(self), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Settings(bot)) 