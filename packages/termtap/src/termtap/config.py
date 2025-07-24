"""termtap configuration - leaf module, no dependencies."""

from pathlib import Path
from typing import Optional, Dict
import tomllib


class TargetConfig:
    """Configuration for a target session."""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.dir = config.get("dir", ".")
        self.start = config.get("start")
        self.env = config.get("env", {})
        self.hover_patterns = config.get("hover_patterns", [])

    @property
    def absolute_dir(self) -> str:
        """Get absolute directory path."""
        return str(Path(self.dir).resolve())


def find_config_file() -> Optional[Path]:
    """Find termtap.toml in current or parent directories."""
    current = Path.cwd()

    for parent in [current] + list(current.parents):
        config_file = parent / "termtap.toml"
        if config_file.exists():
            return config_file

    return None


def load_config(path: Optional[Path] = None) -> Dict[str, TargetConfig]:
    """Load configuration from file.

    Returns dict of target_name -> TargetConfig
    """
    if path is None:
        path = find_config_file()

    if path is None or not path.exists():
        # Return default config only
        return {"default": TargetConfig("default", {})}

    with open(path, "rb") as f:
        data = tomllib.load(f)

    configs = {}

    # Always include default
    configs["default"] = TargetConfig("default", data.get("default", {}))

    # Add other targets
    for name, config in data.items():
        if name != "default" and isinstance(config, dict):
            configs[name] = TargetConfig(name, config)

    return configs


def get_target_config(target: str = "default") -> TargetConfig:
    """Get config for specific target."""
    configs = load_config()
    return configs.get(target, configs["default"])
