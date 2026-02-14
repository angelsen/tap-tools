"""Chrome DevTools Protocol client with native event storage.

Native CDP approach - store events as-is, query on-demand.
Built on browser-level WebSocket multiplexing + DuckDB for minimal overhead.

PUBLIC API:
  - BrowserSession: Browser-level WebSocket with session multiplexing
  - CDPSession: Session-multiplexed CDP client with DuckDB event storage
"""

from webtap.cdp.browser import BrowserSession
from webtap.cdp.session import CDPSession

__all__ = ["BrowserSession", "CDPSession"]
