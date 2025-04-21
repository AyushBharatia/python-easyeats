import discord
import os
import datetime
import logging
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

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