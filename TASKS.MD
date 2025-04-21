# Ticket Bot Settings Implementation

## Tasks for `/settings` Command

1. Create a new cog file `cogs/settings.py` for handling settings-related commands
2. Implement `/settings` slash command that shows an ephemeral embed with configuration options
3. Add settings cog to bot.py initial_extensions list
4. Add the following configuration options to the settings embed:
   - Staff role management (add/remove staff roles)
   - Ticket category configuration
   - Ticket channel configuration (where the ticket creation embed is posted)
   - Transcript channel configuration
   - Cooldown period configuration for ticket creation
   - Custom message templates configuration

## Button Suggestions for Settings Embed

1. **Staff Roles**: Button to open a dropdown to select/deselect staff roles
2. **Channels**: Button to configure ticket channel, category, and transcript channel
3. **Messages**: Button to customize welcome messages and ticket templates
4. **Cooldowns**: Button to adjust ticket creation cooldown times
5. **Save Configuration**: Button to save all settings changes
6. **Reset Defaults**: Button to reset settings to default values
7. **Preview**: Button to preview ticket creation embed with current settings

## Implementation Notes

- All settings interactions should be ephemeral to avoid cluttering channels
- Use modals for text input (custom messages, etc.)
- Implement permission checks to ensure only administrators can modify settings
- Add configuration validation to prevent invalid settings
- Create backup of config before making changes
- Add help text explaining each setting's purpose
