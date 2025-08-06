"""Configuration management for termtap.

Handles init groups and default settings from termtap.toml.
"""

from pathlib import Path
from typing import Optional, Dict
import tomllib
import re

from .types import ExecutionConfig, SessionWindowPane, InitGroup, ServiceConfig


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
    """Manages configuration for termtap."""

    def __init__(self):
        self._config_file = _find_config_file()
        self.data = _load_config(self._config_file)
        self._default_config = self.data.get("default", {})
        self._init_groups: Dict[str, InitGroup] = {}

        # Parse init groups
        for key, value in self.data.items():
            if key == "default" or not isinstance(value, dict):
                continue

            # Check if this is an init group (has services with commands)
            services = []
            layout = value.get("layout", "even-horizontal")

            for service_name, service_data in value.items():
                if service_name == "layout":
                    continue

                if isinstance(service_data, dict) and "command" in service_data:
                    service = ServiceConfig(
                        name=service_name,
                        group=key,
                        pane=service_data.get("pane", len(services)),
                        command=service_data["command"],
                        path=service_data.get("path"),  # New field
                        env=service_data.get("env"),  # New field
                        ready_pattern=service_data.get("ready_pattern"),
                        timeout=service_data.get("timeout"),
                        depends_on=service_data.get("depends_on"),
                    )
                    services.append(service)

            if services:
                self._init_groups[key] = InitGroup(name=key, layout=layout, services=services)

    def get_init_group(self, name: str) -> Optional[InitGroup]:
        """Get init group configuration."""
        return self._init_groups.get(name)

    def list_init_groups(self) -> list[str]:
        """List available init groups."""
        return list(self._init_groups.keys())

    def resolve_service_target(self, target: str) -> Optional[SessionWindowPane]:
        """Resolve dot notation (demo.backend) to session:window.pane.

        Args:
            target: Target in dot notation

        Returns:
            Session:window.pane if resolvable, None otherwise
        """
        if "." not in target:
            return None

        parts = target.split(".", 1)
        if len(parts) != 2:
            return None

        group_name, service_name = parts

        # Find the init group
        group = self._init_groups.get(group_name)
        if not group:
            return None

        # Find the service
        service = group.get_service(service_name)
        if not service:
            return None

        return service.session_window_pane

    def get_execution_config(self, session_window_pane: SessionWindowPane) -> ExecutionConfig:
        """Get execution configuration for a pane.

        Checks init groups first, then falls back to defaults.

        Args:
            session_window_pane: Full pane identifier (e.g., "demo:0.0")

        Returns:
            ExecutionConfig with ready_pattern compiled if present
        """
        # Get defaults
        ready_pattern = self._default_config.get("ready_pattern")
        timeout = self._default_config.get("timeout", 30.0)

        # Extract session name
        session = session_window_pane.split(":")[0]

        # Check if this is part of an init group
        if session in self._init_groups:
            group = self._init_groups[session]
            # Find matching service by pane
            for service in group.services:
                if service.session_window_pane == session_window_pane:
                    if service.ready_pattern:
                        ready_pattern = service.ready_pattern
                    if service.timeout:
                        timeout = service.timeout
                    break

        # Compile pattern if present
        compiled_pattern = None
        if ready_pattern:
            try:
                compiled_pattern = re.compile(ready_pattern)
            except re.error:
                pass

        return ExecutionConfig(
            session_window_pane=session_window_pane,
            ready_pattern=ready_pattern,
            timeout=timeout,
            compiled_pattern=compiled_pattern,
        )

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
    """Get execution configuration for a pane."""
    return get_config_manager().get_execution_config(session_window_pane)


def resolve_service_target(target: str) -> Optional[SessionWindowPane]:
    """Resolve service dot notation."""
    return get_config_manager().resolve_service_target(target)
