"""WebTap command modules for browser automation.

This module imports all command modules to register their decorated functions with the app.
Command functions are automatically registered when their modules are imported.

PUBLIC API:
  - connect: Connect to Chrome page and enable domains
  - disconnect: Disconnect from Chrome
  - clear: Clear various data stores (events, console, cache)
  - pages: List available Chrome pages
  - status: Get connection status
  - navigate: Navigate to URL
  - reload: Reload current page
  - back: Navigate back in history
  - forward: Navigate forward in history
  - page: Get current page information
  - history: Show navigation history
  - js: Execute JavaScript in browser
  - network: Show network requests in table format
  - console: Show console messages
  - inspect: Inspect CDP event by rowid with Python expressions
  - events: Query any CDP events by field values
  - fetch: Enable/disable fetch interception
  - requests: Show paused fetch requests
  - resume: Resume paused fetch requests
  - fail: Fail paused fetch requests
  - body: Get response body for network request
  - filters: Manage network request filters
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
