"""WebTap command modules for browser automation.

This module imports all command modules to register their decorated functions with the app.
Command functions are automatically registered via @app.command when their modules are imported.
"""

# Import all command modules to register them with app
from webtap.commands import (
    connection,
    navigation,
    javascript,
    network,
    console,
    inspect,
    events,
    fetch,
    body,
    filters,
    bootstrap,
)

__all__ = [
    "connection",
    "navigation",
    "javascript",
    "network",
    "console",
    "inspect",
    "events",
    "fetch",
    "body",
    "filters",
    "bootstrap",
]
