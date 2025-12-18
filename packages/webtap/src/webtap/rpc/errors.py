"""RPC error definitions.

PUBLIC API:
  - ErrorCode: Standard JSON-RPC 2.0 error codes
  - RPCError: Structured exception for RPC errors
"""

from typing import Any


class ErrorCode:
    """Standard JSON-RPC 2.0 error codes.

    Attributes:
        METHOD_NOT_FOUND: RPC method not found
        INVALID_STATE: Operation invalid in current state
        STALE_EPOCH: Request epoch does not match current epoch
        INVALID_PARAMS: Invalid or missing parameters
        INTERNAL_ERROR: Internal server error
        NOT_CONNECTED: Not connected to a Chrome page
    """

    METHOD_NOT_FOUND = "METHOD_NOT_FOUND"
    INVALID_STATE = "INVALID_STATE"
    STALE_EPOCH = "STALE_EPOCH"
    INVALID_PARAMS = "INVALID_PARAMS"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_CONNECTED = "NOT_CONNECTED"


class RPCError(Exception):
    """Structured RPC error with code, message, and optional data.

    Args:
        code: Error code from ErrorCode constants
        message: Human-readable error message
        data: Optional additional error details

    Attributes:
        code: Error code
        message: Error message
        data: Additional error details
    """

    def __init__(self, code: str, message: str, data: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(message)
