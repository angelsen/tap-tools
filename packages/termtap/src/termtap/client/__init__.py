"""Termtap daemon client.

PUBLIC API:
  - DaemonClient: Client for communicating with daemon
  - DaemonNotRunning: Exception when daemon is not running
  - RPCError: RPC error from daemon
"""

from .rpc import DaemonClient, DaemonNotRunning, RPCError

__all__ = ["DaemonClient", "DaemonNotRunning", "RPCError"]
