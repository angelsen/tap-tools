"""WebTap RPC Framework.

PUBLIC API:
  - RPCFramework: Core RPC request/response handler
  - RPCError: Exception class for structured errors
  - ErrorCode: Standard RPC error codes
  - ConnectionState: Connection state machine states
"""

from webtap.rpc.errors import ErrorCode, RPCError
from webtap.rpc.framework import RPCFramework
from webtap.rpc.machine import ConnectionState

__all__ = ["RPCFramework", "RPCError", "ErrorCode", "ConnectionState"]
