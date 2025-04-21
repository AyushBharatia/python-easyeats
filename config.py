import json
import os
from typing import Dict, List, Any, Optional

# Default configuration with empty values
DEFAULT_CONFIG = {
    "tickets": {},
    "staff_role_ids": [],
    "ticket_counter": 0,
    "ticket_category_id": None,
    "ticket_channel_id": None,
    "transcript_channel_id": None,  # New setting for transcript channel
    "ticket_cooldown": 30  # Default cooldown period in seconds
}

class Config:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file or create default if not exists"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Error loading config file. Creating new config.")
                return self._create_default_config()
        else:
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        default_config = DEFAULT_CONFIG
        # Set data attribute before saving
        self.data = default_config
        self.save()
        return default_config
    
    def save(self) -> None:
        """Save configuration to JSON file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=4)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        self.data[key] = value
        self.save()
    
    def add_ticket(self, channel_id: int, user_id: int, data: Dict[str, Any]) -> None:
        """Add a ticket to the configuration"""
        if "tickets" not in self.data:
            self.data["tickets"] = {}
        
        self.data["tickets"][str(channel_id)] = {
            "user_id": user_id,
            "status": "open",
            "created_at": data.get("created_at", ""),
            "country": data.get("country", ""),
            "group_link": data.get("group_link", ""),
            "payment_method": data.get("payment_method", ""),
        }
        self.save()
    
    def get_ticket(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get a ticket by channel ID"""
        return self.data.get("tickets", {}).get(str(channel_id))
    
    def update_ticket_status(self, channel_id: int, status: str) -> None:
        """Update a ticket's status"""
        if "tickets" in self.data and str(channel_id) in self.data["tickets"]:
            self.data["tickets"][str(channel_id)]["status"] = status
            self.save()
    
    def delete_ticket(self, channel_id: int) -> None:
        """Delete a ticket from the configuration"""
        if "tickets" in self.data and str(channel_id) in self.data["tickets"]:
            del self.data["tickets"][str(channel_id)]
            self.save()

# Initialize global config instance
config = Config() 