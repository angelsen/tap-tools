"""Chrome DevTools Protocol client with native event storage.

Native CDP approach - store events as-is, query on-demand.
Built on WebSocketApp + DuckDB for minimal overhead.

PUBLIC API:
  - CDPSession: Main CDP client with WebSocket connection and event storage
  - build_query: Dynamic query builder with field discovery
"""

from webtap.cdp.query import build_query
from webtap.cdp.session import CDPSession

__all__ = ["CDPSession", "build_query"]
