"""Configuration management - pane-first architecture.

Supports both session-level and pane-level configuration with
hierarchical resolution: pane > session > default.
"""

from pathlib import Path
from typing import Optional, Dict
import tomllib

from .types import TargetConfig as TypedTargetConfig, PaneConfig, SessionConfig, SessionWindowPane


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
    """Manages pane and session configurations."""
    
    def __init__(self):
        self.data = _load_config()
        self._default_config = self.data.get("default", {})
        self._session_configs: Dict[str, SessionConfig] = {}
        self._pane_configs: Dict[SessionWindowPane, PaneConfig] = {}
        
        # Load session configs
        sessions = self.data.get("sessions", {})
        for session_name, config in sessions.items():
            if isinstance(config, dict):
                self._session_configs[session_name] = SessionConfig(
                    session=session_name,
                    dir=config.get("dir"),
                    env=config.get("env", {})
                )
        
        # Load pane configs
        panes = self.data.get("panes", {})
        for pane_id, config in panes.items():
            if isinstance(config, dict):
                self._pane_configs[pane_id] = PaneConfig(
                    pane_id=pane_id,
                    dir=config.get("dir"),
                    start=config.get("start"),
                    name=config.get("name"),
                    env=config.get("env", {})
                )
    
    def get_config_for_pane(self, session_window_pane: SessionWindowPane) -> TypedTargetConfig:
        """Get resolved configuration for a specific pane.
        
        Resolution order:
        1. Pane-specific config
        2. Session-level config
        3. Default config
        
        Args:
            session_window_pane: Full pane identifier (e.g., "backend:0.0")
            
        Returns:
            Resolved TargetConfig with all values filled
        """
        # Extract session name
        session = session_window_pane.split(':')[0]
        
        # Start with defaults
        dir = self._default_config.get("dir", ".")
        env = self._default_config.get("env", {}).copy()
        start = None
        name = None
        
        # Apply session config if exists
        if session in self._session_configs:
            session_config = self._session_configs[session]
            if session_config.dir:
                dir = session_config.dir
            if session_config.env:
                env.update(session_config.env)
        
        # Apply pane config if exists
        if session_window_pane in self._pane_configs:
            pane_config = self._pane_configs[session_window_pane]
            if pane_config.dir:
                dir = pane_config.dir
            if pane_config.env:
                env.update(pane_config.env)
            if pane_config.start:
                start = pane_config.start
            if pane_config.name:
                name = pane_config.name
        
        return TypedTargetConfig(
            target=session_window_pane,
            dir=dir,
            env=env,
            start=start,
            name=name
        )
    
    def get_config_for_new_session(self, session: str) -> TypedTargetConfig:
        """Get config for creating a new session.
        
        Used when session doesn't exist yet, defaults to first pane.
        
        Args:
            session: Session name
            
        Returns:
            Config for session:0.0
        """
        return self.get_config_for_pane(f"{session}:0.0")
    
    @property
    def skip_processes(self) -> list[str]:
        """Get list of wrapper processes to skip in detection."""
        return self._default_config.get("skip_processes", [
            "uv", "npm", "yarn", "poetry", "pipenv", "nix-shell"
        ])
    
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


def get_pane_config(session_window_pane: SessionWindowPane) -> TypedTargetConfig:
    """Get configuration for a specific pane.
    
    Args:
        session_window_pane: Full pane identifier
        
    Returns:
        Resolved configuration
    """
    return get_config_manager().get_config_for_pane(session_window_pane)


def get_target_config(target: str = "default") -> TypedTargetConfig:
    """Legacy compatibility - converts to pane config.
    
    Args:
        target: Session name or "default"
        
    Returns:
        Config for first pane of session
    """
    if target == "default":
        return get_pane_config("default:0.0")
    else:
        return get_config_manager().get_config_for_new_session(target)