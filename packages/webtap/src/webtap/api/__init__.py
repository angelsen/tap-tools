"""WebTap API service layer.

PUBLIC API:
  - run_daemon_server: Run daemon server (blocking)
  - get_full_state: Get complete WebTap state for SSE broadcasting
"""

from webtap.api.server import run_daemon_server
from webtap.api.state import get_full_state

__all__ = ["run_daemon_server", "get_full_state"]
