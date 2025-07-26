"""Configuration management for termtap sessions.

Provides target-based configuration loading from termtap.toml files
with hierarchical directory searching and default fallbacks.
"""

from pathlib import Path
from typing import Optional, Dict
import tomllib


class TargetConfig:
    """Configuration for a target session.

    Attributes:
        name: Target name identifier.
        dir: Working directory path for the session.
        start: Optional startup command.
        env: Environment variables dictionary.
        hover_patterns: List of patterns for hover dialogs.
        skip_processes: List of wrapper processes to skip in detection.
    """

    def __init__(self, name: str, config: dict):
        self.name = name
        self.dir = config.get("dir", ".")
        self.start = config.get("start")
        self.env = config.get("env", {})
        self.hover_patterns = config.get("hover_patterns", [])
        self.skip_processes = config.get("skip_processes", ["uv", "npm", "yarn", "poetry", "pipenv", "nix-shell"])

    @property
    def absolute_dir(self) -> str:
        """Get absolute directory path.

        Returns:
            Resolved absolute path as string.
        """
        return str(Path(self.dir).resolve())


def _find_config_file() -> Optional[Path]:
    """Find termtap.toml in current or parent directories.

    Returns:
        Path to config file if found, None otherwise.
    """
    current = Path.cwd()

    for parent in [current] + list(current.parents):
        config_file = parent / "termtap.toml"
        if config_file.exists():
            return config_file

    return None


def _load_config(path: Optional[Path] = None) -> Dict[str, TargetConfig]:
    """Load configuration from file.

    Args:
        path: Path to config file. Defaults to None (auto-discover).

    Returns:
        Dictionary mapping target names to TargetConfig instances.
    """
    if path is None:
        path = _find_config_file()

    if path is None or not path.exists():
        return {"default": TargetConfig("default", {})}

    with open(path, "rb") as f:
        data = tomllib.load(f)

    configs = {}

    configs["default"] = TargetConfig("default", data.get("default", {}))
    for name, config in data.items():
        if name != "default" and isinstance(config, dict):
            configs[name] = TargetConfig(name, config)

    return configs


def _get_target_config(target: str = "default") -> TargetConfig:
    """Get config for specific target.

    Args:
        target: Target name to retrieve. Defaults to "default".

    Returns:
        TargetConfig instance for the specified target.
    """
    configs = _load_config()
    return configs.get(target, configs["default"])
