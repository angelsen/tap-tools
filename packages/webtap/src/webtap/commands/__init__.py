"""WebTap commands - import all to register with app."""

# Import all command modules to register them
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
]
