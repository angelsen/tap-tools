"""JSON-RPC 2.0 wire protocol shared by daemon and client.

PUBLIC API:
  - RPCError: RPC error with code/message/data
  - encode: Serialize a message dict to newline-delimited bytes
  - request: Build a JSON-RPC request envelope
  - success_response: Build a JSON-RPC success envelope
  - error_response: Build a JSON-RPC error envelope
  - PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR: Standard error codes
"""

import json
from typing import Any

__all__ = [
    "RPCError",
    "encode",
    "request",
    "success_response",
    "error_response",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
]

# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class RPCError(Exception):
    """JSON-RPC error, raised client-side and serialized daemon-side."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code}] {message}")

    def to_dict(self) -> dict:
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


def encode(message: dict) -> bytes:
    """Serialize a message dict to newline-delimited JSON bytes. The only framing definition."""
    return json.dumps(message).encode() + b"\n"


def request(method: str, params: dict, request_id: Any) -> dict:
    """Build a JSON-RPC request envelope."""
    return {"jsonrpc": "2.0", "method": method, "params": params, "id": request_id}


def success_response(request_id: Any, result: Any) -> dict:
    """Build a JSON-RPC success envelope."""
    return {"jsonrpc": "2.0", "result": result, "id": request_id}


def error_response(request_id: Any, code: int, message: str, data: Any = None) -> dict:
    """Build a JSON-RPC error envelope."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "error": error, "id": request_id}
