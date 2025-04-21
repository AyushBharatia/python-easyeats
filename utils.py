import discord
from typing import Optional, List, Union
import re
import asyncio
import logging
import os
import datetime

logger = logging.getLogger(__name__)

def create_embed(
    title: str, 
    description: str = "", 
    color: int = discord.Color.blue().value,
    fields: Optional[List[dict]] = None,
    footer_text: Optional[str] = None,
    thumbnail_url: Optional[str] = None
) -> discord.Embed:
    """Create a Discord embed with the given parameters"""
    embed = discord.Embed(title=title, description=description, color=color)
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )
    
    if footer_text:
        embed.set_footer(text=footer_text)
    
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    
    return embed

def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL"""
    url_pattern = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(url))

async def get_or_create_category(
    guild: discord.Guild, 
    category_name: str,
    position: Optional[int] = None
) -> discord.CategoryChannel:
    """Get a category by name or create it if it doesn't exist"""
    # First try to find the category
    for category in guild.categories:
        if category.name.lower() == category_name.lower():
            return category
    
    # If category doesn't exist, create it
    permissions = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False)
    }
    
    # Create the category
    category = await guild.create_category(
        name=category_name,
        position=position,
        overwrites=permissions
    )
    
    return category

async def wait_for_message(
    bot: discord.Client,
    user: discord.User,
    channel: discord.TextChannel,
    timeout: int = 60
) -> Optional[discord.Message]:
    """Wait for a message from a specific user in a specific channel"""
    def check(message):
        return message.author == user and message.channel == channel
    
    try:
        message = await bot.wait_for('message', check=check, timeout=timeout)
        return message
    except asyncio.TimeoutError:
        # Handle timeout gracefully
        logger.info(f"Timeout waiting for message from {user} in {channel}")
        return None
    except Exception as e:
        # Log any other errors
        logger.error(f"Error waiting for message: {e}")
        return None

# Transcript utility functions

async def fetch_channel_messages(channel: discord.TextChannel, limit: int = None) -> List[discord.Message]:
    """
    Fetches messages from a channel with pagination support.
    
    Args:
        channel: The Discord channel to fetch messages from
        limit: Maximum number of messages to fetch (None for all available)
        
    Returns:
        List of messages in chronological order (oldest first)
    """
    messages = []
    
    try:
        # Use history with limit to fetch messages
        async for message in channel.history(limit=limit, oldest_first=False):
            messages.append(message)
        
        # Reverse to get chronological order (oldest first)
        messages.reverse()
        
        logger.info(f"Fetched {len(messages)} messages from channel {channel.name}")
        return messages
    
    except discord.Forbidden:
        logger.error(f"Missing permissions to fetch messages from {channel.name}")
        return []
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return []

def format_message(message: discord.Message) -> str:
    """
    Formats a Discord message for a text transcript.
    
    Args:
        message: The Discord message to format
        
    Returns:
        Formatted text string of the message
    """
    # Format timestamp
    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    
    # Format attachments
    attachments = ""
    if message.attachments:
        attachment_links = [f"  - {a.url}" for a in message.attachments]
        attachments = "\nAttachments:\n" + "\n".join(attachment_links)
    
    # Format the message content
    content = message.content or "[No text content]"
    
    # Create the formatted string
    formatted_message = (
        f"[{timestamp}] {message.author.name}#{message.author.discriminator}:\n"
        f"{content}{attachments}\n"
    )
    
    return formatted_message

async def generate_transcript(channel: discord.TextChannel, include_metadata: bool = True) -> str:
    """
    Generates a text transcript from a channel.
    
    Args:
        channel: The Discord channel to create a transcript for
        include_metadata: Whether to include ticket metadata
        
    Returns:
        String containing the formatted transcript
    """
    messages = await fetch_channel_messages(channel)
    
    # Create transcript header
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"# Transcript of #{channel.name}\n"
    header += f"Generated on: {current_time}\n"
    
    if include_metadata:
        # Add ticket metadata if this is a ticket channel
        header += f"Channel ID: {channel.id}\n"
        header += f"Guild: {channel.guild.name}\n\n"
    
    header += "---\n\n"
    
    # Format each message
    message_texts = [format_message(msg) for msg in messages]
    
    # Combine everything into the transcript
    transcript = header + "\n\n".join(message_texts)
    
    return transcript

async def save_transcript(transcript: str, channel_id: int, directory: str = "transcripts") -> Optional[str]:
    """
    Saves a transcript to a file.
    
    Args:
        transcript: The transcript text content
        channel_id: ID of the channel for naming
        directory: Directory to save transcript in
        
    Returns:
        Path to the saved transcript file or None if failed
    """
    try:
        # Create the directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Generate filename based on channel ID and current time
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{directory}/transcript_{channel_id}_{timestamp}.txt"
        
        # Write transcript to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(transcript)
        
        logger.info(f"Transcript saved to {filename}")
        return filename
    
    except Exception as e:
        logger.error(f"Error saving transcript: {e}")
        return None 