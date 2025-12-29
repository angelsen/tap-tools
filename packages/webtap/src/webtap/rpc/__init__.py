"""WebTap RPC Framework.

PUBLIC API:
  - RPCFramework: Core RPC request/response handler
  - RPCContext: Context passed to RPC handlers
  - HandlerMeta: Metadata for RPC handler registration
  - RPCError: Exception class for structured errors
  - ErrorCode: Standard RPC error codes
"""

from webtap.rpc.errors import ErrorCode, RPCError
from webtap.rpc.framework import HandlerMeta, RPCContext, RPCFramework

__all__ = ["RPCFramework", "RPCContext", "HandlerMeta", "RPCError", "ErrorCode"]
