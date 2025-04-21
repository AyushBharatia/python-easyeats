# Discord Ticket Bot

A Discord bot for managing support tickets with an interactive ticket creation flow.

## Features

- **Interactive Ticket Creation** - Users click a button to create a ticket, then complete a questionnaire within the ticket channel
- **Customizable Ticket Flow** - Collects country, group link, and payment method preferences directly in the ticket
- **Ticket Management Commands** - Add/remove users, close tickets, delete tickets
- **Persistent Configuration** - All settings and tickets are stored persistently using JSON
- **Error Handling** - Robust error handling and cooldowns to prevent abuse
- **Staff Role Management** - Set up staff roles with special permissions for tickets

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Discord bot token:
   ```
   BOT_TOKEN=your_bot_token_here
   GUILD_ID=your_guild_id_here
   CLIENT_ID=your_bot_client_id_here
   ```
4. Run the bot:
   ```
   python bot.py
   ```

## Commands

### Admin Commands

- `/setup_ticket [channel]` - Sets up the ticket system in the specified channel or current channel
- `/set_staff <role>` - Adds a role as staff for tickets
- `/remove_staff <role>` - Removes a role from staff for tickets

### Ticket Management Commands

- `/ticket_add <user>` - Adds a user to the current ticket channel
- `/ticket_remove <user>` - Removes a user from the current ticket channel
- `/ticket_close` - Closes the current ticket (archives it)
- `/ticket_delete` - Permanently deletes the current ticket

## Ticket Creation Flow

The ticket creation process works as follows:

1. User clicks the "Create Ticket" button in a designated channel
2. A ticket channel is immediately created and the user is notified
3. **Inside the ticket channel**, the user completes a questionnaire:
   - Selects their country (Canada or US)
   - Indicates if they have a group link to share
   - If yes, they are prompted to send the link in the ticket channel
   - Selects their preferred payment method
4. After completing the questionnaire, a summary is posted in the ticket and staff are notified

This approach keeps all interactions within the ticket channel, making it easier to track conversations and provide support.

## Configuration

All configuration is stored in `config.json`, which is created automatically. This includes:

- Ticket embed message and channel IDs
- Purchase category ID
- Staff role IDs
- Ticket information (channel, user, status, etc.)

## License

MIT License

## Credits

Built with Discord.py 