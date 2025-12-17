"""WebTap API package.

PUBLIC API:
  - run_daemon_server: Run daemon server (blocking)
"""

from webtap.api.server import run_daemon_server

__all__ = ["run_daemon_server"]
