"""Chrome DevTools Protocol client with native event storage.

Native CDP approach - store events as-is, query on-demand.
Built on WebSocketApp + DuckDB for minimal overhead.

PUBLIC API:
  - CDPSession: Main CDP client with WebSocket connection and event storage
"""

from webtap.cdp.session import CDPSession

__all__ = ["CDPSession"]
