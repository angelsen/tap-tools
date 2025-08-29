"""Main application entry point for WebTap browser debugger.

Provides dual REPL/MCP functionality for Chrome DevTools Protocol interaction.
Built on ReplKit2 framework with CDP-native design for browser debugging and
automation leveraging Chrome's native debugging protocol.
"""

from dataclasses import dataclass, field
from typing import Dict, Any

from replkit2 import App

from webtap.cdp import CDPSession


@dataclass
class WebTapState:
    """Application state for WebTap browser debugging.

    Maintains CDP session and connection state for browser interaction.

    Attributes:
        cdp: Chrome DevTools Protocol session instance.
        cache: Dict of caches for different data types.
        _cache_counters: Internal counters for cache ID generation.
    """

    cdp: CDPSession = field(default_factory=CDPSession)
    cache: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "event": {},  # From events() command
        "storage": {},  # From storage commands (future)
    })
    _cache_counters: Dict[str, int] = field(default_factory=lambda: {
        "event": 1,
        "storage": 1,
    })
    
    def cache_add(self, cache_type: str, data: dict) -> str:
        """Add to specific cache and return ID.
        
        Args:
            cache_type: Type of cache ('event', 'storage')
            data: Data to cache
            
        Returns:
            Generated cache ID (e.g., 'ev1', 's1')
        """
        # Use meaningful prefixes
        prefix_map = {
            "event": "ev",  # event value
            "storage": "s"   # storage item
        }
        prefix = prefix_map.get(cache_type, cache_type[0])
        cache_id = f"{prefix}{self._cache_counters[cache_type]}"
        self._cache_counters[cache_type] += 1
        self.cache[cache_type][cache_id] = data
        return cache_id
    
    def cache_clear(self, cache_type: str):
        """Clear specific cache.
        
        Args:
            cache_type: Type of cache to clear
        """
        self.cache[cache_type].clear()
        self._cache_counters[cache_type] = 1


# Must be created before command imports for decorator registration
app = App(
    "webtap",
    WebTapState,
    uri_scheme="webtap",
    fastmcp={
        "description": "Chrome DevTools Protocol debugger",
        "tags": {"browser", "debugging", "chrome", "cdp"},
    },
)


# Command imports trigger @app.command decorator registration
from webtap.commands import connection  # noqa: E402, F401
from webtap.commands import navigation  # noqa: E402, F401
from webtap.commands import execution  # noqa: E402, F401
from webtap.commands import network  # noqa: E402, F401
from webtap.commands import console  # noqa: E402, F401
from webtap.commands import events  # noqa: E402, F401
from webtap.commands import filters  # noqa: E402, F401
from webtap.commands import inspect  # noqa: E402, F401


# Entry point is in __init__.py:main() as specified in pyproject.toml
