"""Termtap daemon client.

PUBLIC API:
  - DaemonClient: Client for communicating with daemon
  - DaemonNotRunning: Exception when daemon is not running
"""

from .rpc import DaemonClient, DaemonNotRunning

__all__ = ["DaemonClient", "DaemonNotRunning"]
