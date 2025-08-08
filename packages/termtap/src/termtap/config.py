"""Configuration management system for termtap applications.

Centralized configuration loading from termtap.toml files with support
for init groups, service definitions, and execution settings.

PUBLIC API:
  - get_config_manager: Get singleton configuration manager
  - get_execution_config: Get execution configuration for a pane
  - resolve_service_target: Resolve service dot notation
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
    """Central configuration manager for termtap applications.

    Loads and manages termtap.toml configuration files, parsing init groups
    and service definitions. Provides service name resolution and execution
    configuration lookup.

    Attributes:
        data: Raw configuration data from termtap.toml
        _config_file: Path to the loaded configuration file
        _default_config: Default configuration section
        _init_groups: Parsed init group configurations
    """

    def __init__(self):
        self._config_file = _find_config_file()
        self.data = _load_config(self._config_file)
        self._default_config = self.data.get("default", {})
        self._init_groups: Dict[str, InitGroup] = {}
        self._parse_init_groups()

    def _parse_init_groups(self):
        """Parse init groups from configuration data."""
        for key, value in self.data.items():
            if key == "default" or not isinstance(value, dict):
                continue

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
                        path=service_data.get("path"),
                        env=service_data.get("env"),
                        ready_pattern=service_data.get("ready_pattern"),
                        timeout=service_data.get("timeout"),
                        depends_on=service_data.get("depends_on"),
                    )
                    services.append(service)

            if services:
                self._init_groups[key] = InitGroup(name=key, layout=layout, services=services)

    def get_init_group(self, name: str) -> Optional[InitGroup]:
        """Get init group configuration by name.

        Args:
            name: Name of the init group to retrieve.

        Returns:
            InitGroup configuration or None if not found.
        """
        return self._init_groups.get(name)

    def list_init_groups(self) -> list[str]:
        """List all available init group names.

        Returns:
            List of init group names from the configuration.
        """
        return list(self._init_groups.keys())

    def resolve_service_target(self, target: str) -> Optional[SessionWindowPane]:
        """Resolve dot notation service target to session:window.pane format.

        Converts service targets like "demo.backend" to full pane identifiers
        like "demo:0.0" based on init group configuration.

        Args:
            target: Service target in dot notation (group.service).

        Returns:
            Full session:window.pane identifier if resolvable, None otherwise.
        """
        if "." not in target:
            return None

        parts = target.split(".", 1)
        if len(parts) != 2:
            return None

        group_name, service_name = parts

        group = self._init_groups.get(group_name)
        if not group:
            return None

        service = group.get_service(service_name)
        if not service:
            return None

        return service.session_window_pane

    def get_execution_config(self, session_window_pane: SessionWindowPane) -> ExecutionConfig:
        """Get execution configuration for a specific pane.

        Builds execution configuration by checking init groups first for service-specific
        settings, then falling back to defaults from the configuration file.

        Args:
            session_window_pane: Full pane identifier (e.g., "demo:0.0").

        Returns:
            ExecutionConfig with compiled ready_pattern if present.
        """
        ready_pattern = self._default_config.get("ready_pattern")
        timeout = self._default_config.get("timeout", 30.0)

        session = session_window_pane.split(":")[0]
        ready_pattern, timeout = self._get_service_overrides(session, session_window_pane, ready_pattern, timeout)

        compiled_pattern = self._compile_ready_pattern(ready_pattern)

        return ExecutionConfig(
            session_window_pane=session_window_pane,
            ready_pattern=ready_pattern,
            timeout=timeout,
            compiled_pattern=compiled_pattern,
        )

    def _get_service_overrides(
        self, session: str, session_window_pane: SessionWindowPane, ready_pattern: Optional[str], timeout: float
    ) -> tuple[Optional[str], float]:
        """Get service-specific configuration overrides."""
        if session in self._init_groups:
            group = self._init_groups[session]
            for service in group.services:
                if service.session_window_pane == session_window_pane:
                    if service.ready_pattern:
                        ready_pattern = service.ready_pattern
                    if service.timeout:
                        timeout = service.timeout
                    break
        return ready_pattern, timeout

    def _compile_ready_pattern(self, ready_pattern: Optional[str]) -> Optional[re.Pattern]:
        """Compile regex pattern for ready detection."""
        if not ready_pattern:
            return None
        try:
            return re.compile(ready_pattern)
        except re.error:
            # Silently ignore malformed patterns
            return None

    @property
    def skip_processes(self) -> list[str]:
        """Get list of wrapper processes to skip in process detection.

        Returns:
            List of process names to skip when detecting primary process.
        """
        return self._default_config.get("skip_processes", ["uv", "npm", "yarn", "poetry", "pipenv", "nix-shell"])

    @property
    def hover_patterns(self) -> list[dict]:
        """Get hover dialog patterns for dangerous commands.

        Returns:
            List of pattern dictionaries for hover dialog triggers.
        """
        return self._default_config.get("hover_patterns", [])


_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create the global configuration manager singleton.

    Returns:
        The global ConfigManager instance, creating it if needed.
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_execution_config(session_window_pane: SessionWindowPane) -> ExecutionConfig:
    """Get execution configuration for a pane using the global manager.

    Args:
        session_window_pane: Full pane identifier (e.g., "demo:0.0").

    Returns:
        ExecutionConfig for the specified pane.
    """
    return get_config_manager().get_execution_config(session_window_pane)


def resolve_service_target(target: str) -> Optional[SessionWindowPane]:
    """Resolve service dot notation using the global manager.

    Args:
        target: Service target in dot notation (group.service).

    Returns:
        Full session:window.pane identifier if resolvable, None otherwise.
    """
    return get_config_manager().resolve_service_target(target)
