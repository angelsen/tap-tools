"""Configuration management - pane-first architecture.

Supports both session-level and pane-level configuration with
hierarchical resolution: pane > session > default.
"""

from pathlib import Path
from typing import Optional, Dict
import tomllib

import re
from .types import ExecutionConfig, SessionConfig, SessionWindowPane


def _find_config_file() -> Optional[Path]:
    """Find termtap.toml in current or parent directories."""
    current = Path.cwd()

    for parent in [current] + list(current.parents):
        config_file = parent / "termtap.toml"
        if config_file.exists():
            return config_file

    return None


def _load_config(path: Optional[Path] = None) -> dict:
    """Load raw configuration from file."""
    if path is None:
        path = _find_config_file()

    if path is None or not path.exists():
        return {}

    with open(path, "rb") as f:
        return tomllib.load(f)


class ConfigManager:
    """Manages session configurations for execution."""

    def __init__(self):
        self.data = _load_config()
        self._default_config = self.data.get("default", {})
        self._session_configs: Dict[str, SessionConfig] = {}

        # Load session configs with ready_pattern and timeout
        sessions = self.data.get("sessions", {})
        for session_name, config in sessions.items():
            if isinstance(config, dict):
                self._session_configs[session_name] = SessionConfig(
                    session=session_name, ready_pattern=config.get("ready_pattern"), timeout=config.get("timeout")
                )

    def get_execution_config(self, session_window_pane: SessionWindowPane) -> ExecutionConfig:
        """Get execution configuration for a pane.

        Resolution order:
        1. Exact pane match (backend:0.0)
        2. Session match (backend)
        3. Default config

        Args:
            session_window_pane: Full pane identifier (e.g., "backend:0.0")

        Returns:
            ExecutionConfig with ready_pattern compiled if present
        """
        # Get defaults
        ready_pattern = self._default_config.get("ready_pattern")
        timeout = self._default_config.get("timeout")

        # Extract session name
        session = session_window_pane.split(":")[0]

        # Check for session-level config
        if session in self._session_configs:
            session_config = self._session_configs[session]
            if session_config.ready_pattern is not None:
                ready_pattern = session_config.ready_pattern
            if session_config.timeout is not None:
                timeout = session_config.timeout

        # Check for exact pane match (overrides session config)
        if session_window_pane in self._session_configs:
            pane_config = self._session_configs[session_window_pane]
            if pane_config.ready_pattern is not None:
                ready_pattern = pane_config.ready_pattern
            if pane_config.timeout is not None:
                timeout = pane_config.timeout

        # Compile pattern if present
        compiled_pattern = None
        if ready_pattern:
            try:
                compiled_pattern = re.compile(ready_pattern)
            except re.error:
                # Invalid regex - just skip it
                pass

        return ExecutionConfig(
            session_window_pane=session_window_pane,
            ready_pattern=ready_pattern,
            timeout=timeout,
            compiled_pattern=compiled_pattern,
        )

    def get_config_for_new_session(self, session: str) -> ExecutionConfig:
        """Get config for creating a new session.

        Args:
            session: Session name

        Returns:
            Config for session:0.0
        """
        return self.get_execution_config(f"{session}:0.0")

    @property
    def skip_processes(self) -> list[str]:
        """Get list of wrapper processes to skip in detection."""
        return self._default_config.get("skip_processes", ["uv", "npm", "yarn", "poetry", "pipenv", "nix-shell"])

    @property
    def hover_patterns(self) -> list[dict]:
        """Get hover dialog patterns."""
        return self._default_config.get("hover_patterns", [])


# Global instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create the global config manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_execution_config(session_window_pane: SessionWindowPane) -> ExecutionConfig:
    """Get execution configuration for a pane.

    Args:
        session_window_pane: Full pane identifier

    Returns:
        ExecutionConfig with compiled pattern
    """
    return get_config_manager().get_execution_config(session_window_pane)
