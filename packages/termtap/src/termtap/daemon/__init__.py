"""Termtap daemon package.

PUBLIC API:
  - TermtapDaemon: Main daemon server class (import from daemon.server)
  - RPCDispatcher: JSON-RPC request dispatcher
"""

from .rpc import RPCDispatcher

__all__ = ["RPCDispatcher"]
