import os
import json
import logging
from typing import Any, Dict

logger = logging.getLogger("discord_bot.config")

CONFIG_PATH = os.getenv("CONFIG_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json"))

DEFAULT_CONFIG: Dict[str, Any] = {
    "guild_id": None,
    "admin_role_id": None,
    "temp_voice": {
        "enabled": True,
        "generator_channel_id": None,
        "category_id": None,
        "name_format": "🔊 {username}'s Room"
    },
    "tickets": {
        "enabled": True,
        "category_id": None,
        "support_role_id": None,
        "types": {
            "support": {
                "name": "Support",
                "emoji": "🎫",
                "description": "Get help from the staff team"
            },
            "report": {
                "name": "Report",
                "emoji": "🚨",
                "description": "Report a player or problem"
            },
            "application": {
                "name": "Application",
                "emoji": "📝",
                "description": "Apply for staff or roles"
            },
            "other": {
                "name": "Other",
                "emoji": "❓",
                "description": "Other inquiries"
            }
        }
    }
}

class ConfigManager:
    def __init__(self, filepath: str = CONFIG_PATH):
        self.filepath = filepath
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.filepath):
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            self.data = DEFAULT_CONFIG.copy()
            self.save()
            return self.data

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading config from {self.filepath}: {e}")
            self.data = DEFAULT_CONFIG.copy()

        return self.data

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            temp_path = f"{self.filepath}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            os.replace(temp_path, self.filepath)
        except Exception as e:
            logger.error(f"Error saving config to {self.filepath}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def update_nested(self, keys: list, value: Any) -> None:
        curr = self.data
        for k in keys[:-1]:
            if k not in curr or not isinstance(curr[k], dict):
                curr[k] = {}
            curr = curr[k]
        curr[keys[-1]] = value
        self.save()
