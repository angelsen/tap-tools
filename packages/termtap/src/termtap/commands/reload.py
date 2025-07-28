"""Utility commands."""

from ..app import app


@app.command(fastmcp={"enabled": False})
def reload(state) -> str:
    """Reload configuration from termtap.toml."""
    from .. import config

    config._config_manager = None
    return "Configuration reloaded"
