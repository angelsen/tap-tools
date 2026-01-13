"""Configuration for termtap daemon.

PUBLIC API:
  - Config: Configuration dataclass
  - load_config: Load config from YAML
  - save_config: Save config to YAML
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from .paths import CONFIG_PATH

__all__ = ["Config", "load_config", "save_config"]


@dataclass
class Config:
    """Termtap configuration."""

    # UI settings
    ui_mode: str = "companion"  # "companion" | "popup" | "none"

    # Daemon settings
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create Config from dict."""
        ui = data.get("ui", {})
        daemon = data.get("daemon", {})

        return cls(
            ui_mode=ui.get("mode", "companion"),
            log_level=daemon.get("log_level", "INFO"),
        )

    def to_dict(self) -> dict:
        """Convert to dict for YAML serialization."""
        return {
            "ui": {
                "mode": self.ui_mode,
            },
            "daemon": {
                "log_level": self.log_level,
            },
        }


def load_config() -> Config:
    """Load config from YAML file.

    Returns default config if file doesn't exist or is invalid.
    """
    if not CONFIG_PATH.exists():
        return Config()

    try:
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f) or {}
        return Config.from_dict(data)
    except (yaml.YAMLError, IOError):
        return Config()


def save_config(config: Config):
    """Save config to YAML file (atomic write)."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write
    with tempfile.NamedTemporaryFile(mode="w", dir=CONFIG_PATH.parent, delete=False, suffix=".yaml") as f:
        yaml.safe_dump(config.to_dict(), f, default_flow_style=False)
        temp_path = Path(f.name)

    temp_path.rename(CONFIG_PATH)
