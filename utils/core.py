import discord
from typing import Optional, List, Union
import re
import asyncio
import logging
import os
import datetime
import html

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

async def generate_transcript(channel: discord.TextChannel, include_metadata: bool = True, format_type: str = "text") -> Union[str, dict]:
    """
    Generates a transcript from a channel.
    
    Args:
        channel: The Discord channel to create a transcript for
        include_metadata: Whether to include ticket metadata
        format_type: Type of transcript to generate ("text" or "html")
        
    Returns:
        String containing the formatted transcript or dict with HTML content and CSS
    """
    messages = await fetch_channel_messages(channel)
    
    if format_type == "html":
        return generate_html_transcript(channel, messages, include_metadata)
    else:
        # Text transcript (default)
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

def generate_html_transcript(channel: discord.TextChannel, messages: List[discord.Message], include_metadata: bool = True) -> dict:
    """
    Generates an HTML transcript from a channel.
    
    Args:
        channel: The Discord channel
        messages: List of messages to include
        include_metadata: Whether to include ticket metadata
        
    Returns:
        Dict containing HTML content and CSS
    """
    # CSS styles for the HTML transcript
    css = """
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        margin: 0;
        padding: 20px;
        color: #2e3338;
        background-color: #f9f9f9;
        line-height: 1.5;
    }
    .transcript-container {
        max-width: 900px;
        margin: 0 auto;
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        overflow: hidden;
    }
    .transcript-header {
        background-color: #5865f2;
        color: white;
        padding: 20px;
        border-bottom: 1px solid #4752c4;
    }
    .transcript-header h1 {
        margin: 0;
        font-size: 24px;
    }
    .transcript-header .ticket-info {
        font-size: 14px;
        margin-top: 5px;
    }
    .transcript-body {
        padding: 10px 20px;
    }
    .message {
        padding: 10px 0;
        border-bottom: 1px solid #e3e5e8;
    }
    .message:nth-child(odd) {
        background-color: #f6f7f9;
    }
    .message-info {
        display: flex;
        align-items: center;
        margin-bottom: 5px;
    }
    .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        margin-right: 10px;
    }
    .username {
        font-weight: bold;
        color: #5865f2;
    }
    .timestamp {
        font-size: 12px;
        color: #8e9297;
        margin-left: 10px;
    }
    .content {
        padding-left: 50px;
        overflow-wrap: break-word;
    }
    .attachments {
        margin-top: 5px;
        padding-left: 50px;
    }
    .attachment {
        display: block;
        margin: 5px 0;
    }
    .attachment a {
        color: #00b0f4;
        text-decoration: none;
    }
    .attachment a:hover {
        text-decoration: underline;
    }
    .collapsible {
        background-color: #f2f3f5;
        cursor: pointer;
        padding: 10px;
        width: 100%;
        border: none;
        text-align: left;
        outline: none;
        font-size: 16px;
        border-radius: 4px;
        margin-top: 10px;
    }
    .active, .collapsible:hover {
        background-color: #e3e5e8;
    }
    .collapsible-content {
        padding: 0 10px;
        max-height: 0;
        overflow: hidden;
        transition: max-height 0.2s ease-out;
        background-color: #f9f9fa;
    }
    """
    
    # Create HTML header
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Transcript of {channel.name}</title>
        <style id="transcript-css">{css}</style>
    </head>
    <body>
        <div class="transcript-container">
            <div class="transcript-header">
                <h1>Transcript of #{channel.name}</h1>
                <div class="ticket-info">
                    <p>Generated on: {current_time}</p>
    """
    
    if include_metadata:
        html_content += f"""
                    <p>Channel ID: {channel.id}</p>
                    <p>Guild: {html.escape(channel.guild.name)}</p>
        """
    
    html_content += """
                </div>
            </div>
            <div class="transcript-body">
    """
    
    # Format each message
    for msg in messages:
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        
        # Get avatar URL or use a default
        avatar_url = msg.author.display_avatar.url if hasattr(msg.author, 'display_avatar') else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        # Format the message content with HTML escaping
        content = html.escape(msg.content) if msg.content else "[No text content]"
        # Replace Discord newlines with HTML breaks
        content = content.replace('\n', '<br>')
        
        # Start message HTML
        html_content += f"""
            <div class="message">
                <div class="message-info">
                    <img src="{avatar_url}" class="avatar" alt="Avatar">
                    <span class="username">{html.escape(msg.author.name)}</span>
                    <span class="timestamp">{timestamp}</span>
                </div>
                <div class="content">{content}</div>
        """
        
        # Add attachments if any
        if msg.attachments:
            html_content += '<div class="attachments">'
            for attachment in msg.attachments:
                html_content += f'<div class="attachment"><a href="{attachment.url}" target="_blank">{html.escape(attachment.filename)}</a></div>'
            html_content += '</div>'
        
        # Close message div
        html_content += """
            </div>
        """
    
    # Add JavaScript for collapsible sections
    html_content += """
            </div>
        </div>
        <script>
            document.addEventListener("DOMContentLoaded", function() {
                var coll = document.getElementsByClassName("collapsible");
                for (var i = 0; i < coll.length; i++) {
                    coll[i].addEventListener("click", function() {
                        this.classList.toggle("active");
                        var content = this.nextElementSibling;
                        if (content.style.maxHeight) {
                            content.style.maxHeight = null;
                        } else {
                            content.style.maxHeight = content.scrollHeight + "px";
                        }
                    });
                }
            });
        </script>
    </body>
    </html>
    """
    
    return {
        "html_content": html_content,
        "css": css
    }

async def save_transcript(transcript: Union[str, dict], channel_id: int, directory: str = "transcripts") -> Optional[str]:
    """
    Saves a transcript to a file.
    
    Args:
        transcript: The transcript content (text or HTML dict)
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
        
        if isinstance(transcript, dict):
            # This is an HTML transcript
            filename = f"{directory}/transcript_{channel_id}_{timestamp}.html"
            content = transcript["html_content"]
        else:
            # This is a text transcript
            filename = f"{directory}/transcript_{channel_id}_{timestamp}.txt"
            content = transcript
        
        # Write transcript to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Transcript saved to {filename}")
        return filename
    
    except Exception as e:
        logger.error(f"Error saving transcript: {e}")
        return None

# Transcript search utilities

def search_transcripts(
    directory: str = "transcripts", 
    query: str = None, 
    user: str = None, 
    date_from: str = None, 
    date_to: str = None,
    limit: int = 100
) -> List[dict]:
    """
    Search through transcript files with various filters.
    
    Args:
        directory: Directory containing transcript files
        query: Text to search for in transcript content
        user: Username to filter messages by
        date_from: Start date in YYYY-MM-DD format
        date_to: End date in YYYY-MM-DD format
        limit: Maximum number of results to return
        
    Returns:
        List of dictionaries with search results
    """
    results = []
    
    try:
        # Check if directory exists
        if not os.path.exists(directory):
            logger.error(f"Transcript directory {directory} does not exist")
            return results
        
        # Process date filters
        from_date = None
        to_date = None
        
        if date_from:
            try:
                from_date = datetime.datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid from_date format: {date_from}")
        
        if date_to:
            try:
                to_date = datetime.datetime.strptime(date_to, "%Y-%m-%d")
                # Set to end of day
                to_date = to_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                logger.error(f"Invalid to_date format: {date_to}")
        
        # Get list of transcript files
        files = [f for f in os.listdir(directory) if f.endswith('.txt') or f.endswith('.html')]
        
        # Process each file
        for filename in files:
            file_path = os.path.join(directory, filename)
            
            # Get file creation date from the file name
            # Format is transcript_channelid_YYYYMMDD_HHMMSS.txt or .html
            file_date_str = None
            if '_' in filename:
                try:
                    date_part = filename.split('_')[-2] + '_' + filename.split('_')[-1].split('.')[0]
                    file_date = datetime.datetime.strptime(date_part, "%Y%m%d_%H%M%S")
                    file_date_str = file_date.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Apply date filters
                    if from_date and file_date < from_date:
                        continue
                    if to_date and file_date > to_date:
                        continue
                except (ValueError, IndexError):
                    # If date parsing fails, skip date filtering for this file
                    logger.warning(f"Could not parse date from filename: {filename}")
            
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    
                    # Skip HTML files if we can't handle them properly
                    if filename.endswith('.html') and not query:
                        # For HTML files we only support direct text search, not user search
                        continue
                    
                    # Apply text search filter
                    if query and query.lower() not in content.lower():
                        continue
                    
                    # Apply user filter for text files
                    if user and filename.endswith('.txt'):
                        # Look for format like "[YYYY-MM-DD HH:MM:SS] username#discriminator:" or "username:"
                        user_pattern = rf"\[\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}\] {re.escape(user)}[^:]*:"
                        if not re.search(user_pattern, content, re.IGNORECASE):
                            # Try alternate pattern with just username
                            user_pattern = rf"{re.escape(user)}[^:]*:"
                            if not re.search(user_pattern, content, re.IGNORECASE):
                                continue
                    
                    # Extract channel ID from filename
                    channel_id = None
                    try:
                        channel_id = filename.split('_')[1]
                    except (IndexError, ValueError):
                        pass
                    
                    # Add to results
                    results.append({
                        "filename": filename,
                        "path": file_path,
                        "date": file_date_str,
                        "channel_id": channel_id,
                        "preview": content[:200] + "..." if len(content) > 200 else content
                    })
                    
                    # Check if we've reached the limit
                    if len(results) >= limit:
                        break
            
            except Exception as e:
                logger.error(f"Error reading file {filename}: {e}")
        
        # Sort results by date (newest first)
        results.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        return results[:limit]  # Apply limit again just to be safe
    
    except Exception as e:
        logger.error(f"Error searching transcripts: {e}")
        return []

async def format_search_results(results: List[dict]) -> dict:
    """
    Format search results for display in Discord.
    
    Args:
        results: List of search result dictionaries
        
    Returns:
        Dict with formatted content for embed and fields
    """
    if not results:
        return {
            "title": "Transcript Search Results",
            "description": "No transcripts found matching your search criteria.",
            "fields": []
        }
    
    # Create formatted output
    description = f"Found {len(results)} transcript(s) matching your search criteria."
    
    # Create fields for each result
    fields = []
    for i, result in enumerate(results[:10]):  # Limit to 10 for embed
        filename = result.get("filename", "Unknown")
        date = result.get("date", "Unknown date")
        channel_id = result.get("channel_id", "Unknown")
        
        field_name = f"{i+1}. Transcript from {date}"
        field_value = f"Channel ID: {channel_id}\nFilename: {filename}\n"
        
        fields.append({
            "name": field_name,
            "value": field_value,
            "inline": False
        })
    
    # Add note if results were truncated
    if len(results) > 10:
        description += "\n⚠️ Showing only the first 10 results."
    
    return {
        "title": "Transcript Search Results",
        "description": description,
        "fields": fields
    } 