# Discord Ticket Bot - Implementation Overview

This document provides a detailed overview of the implementation of the Discord Ticket Bot.

## Project Structure

- **bot.py** - Main bot file that initializes the Discord bot and loads all cogs
- **config.py** - Configuration manager for persistent storage
- **utils.py** - Utility functions used throughout the bot
- **cogs/** - Directory containing all bot commands and features
  - **tickets.py** - Handles ticket creation process and persistent embed
  - **ticket_management.py** - Handles ticket management commands
  - **error_handler.py** - Global error handling for all commands

## Core Components

### Bot Class (`TicketBot`)

The main bot class extends `commands.Bot` from discord.py and handles:
- Setting up and configuring intents
- Loading all cogs (tickets, ticket_management, error_handler)
- Syncing slash commands with Discord
- Setting the bot's status/presence

### Configuration System

The configuration system uses a JSON file to store persistent data:
- Ticket embed message and channel IDs
- Purchase category ID
- Staff role IDs
- Ticket information (channel ID, user ID, status, etc.)

The `Config` class provides methods to:
- Load and save configuration data
- Add, update, and delete tickets
- Get and set configuration values

### Ticket Creation Flow

The ticket creation process is implemented using Discord's view and interaction system:
1. A persistent embed with a "Create Ticket" button is set up in a designated channel
2. When the button is clicked, a ticket channel is immediately created
3. The user is directed to the new ticket channel to complete a questionnaire:
   - Country selection using buttons
   - Group link query using buttons
   - Payment method selection using a dropdown menu
4. After all information is collected, a summary embed is posted in the ticket channel and staff are notified

This in-channel flow provides a better user experience and keeps all interactions in one place.

### Button & View System

Several custom views are implemented for interactive elements:
- `TicketView` - Persistent view with the "Create Ticket" button
- `CountrySelectionView` - Buttons for selecting Canada or US
- `GroupLinkView` - Yes/No buttons for group link query
- `PaymentMethodView` - Dropdown for selecting payment method
- `ConfirmationView` - Confirm/Cancel buttons for closing/deleting tickets

### Permission System

The permission system ensures only authorized users can perform ticket actions:
- Administrators can always perform any action
- Staff roles (configured via `/set_staff`) have management permissions
- Ticket creators have specific permissions in their tickets
- Each command performs permission checks before execution

### Error Handling

The error handler cog provides global error handling for:
- Command cooldowns
- Missing permissions
- API errors
- General exceptions

## Discord.py Integration

The bot utilizes several discord.py features:
- Slash commands via `app_commands`
- Button interactions via `discord.ui.Button`
- Dropdown menus via `discord.ui.Select`
- Views for interactive components
- Permission overrides for channel permissions
- Cogs for command organization

## Data Flow

1. User interacts with the persistent ticket embed in a public channel
2. A ticket channel is created with proper permissions
3. The user completes a questionnaire within the ticket channel
4. Data is collected and stored in the configuration
5. A summary is posted in the ticket channel
6. Users and staff can manage the ticket with slash commands

## Future Improvements

Potential areas for enhancement:
- Database integration for larger scale deployments
- More customization options for ticket templates
- Ticket transcripts/archiving
- Web dashboard for management
- Analytics and reporting features 