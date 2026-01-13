"""JSON-RPC 2.0 dispatcher for termtap daemon.

PUBLIC API:
  - RPCDispatcher: Register and dispatch JSON-RPC methods
  - RPCError: RPC error with code and message
"""

import json
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

__all__ = ["RPCDispatcher", "RPCError"]


# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Custom error codes
DAEMON_NOT_RUNNING = -32000
INVALID_TARGET = -32001
PANE_NOT_FOUND = -32002
SEND_FAILED = -32003
TIMEOUT = -32004
QUEUE_FULL = -32005


@dataclass
class RPCError(Exception):
    """JSON-RPC error."""

    code: int
    message: str
    data: Any = None

    def to_dict(self) -> dict:
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


class RPCDispatcher:
    """JSON-RPC 2.0 method dispatcher."""

    def __init__(self):
        self._methods: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register(self, name: str, handler: Callable[..., Awaitable[Any]]):
        """Register an async method handler."""
        self._methods[name] = handler

    def method(self, name: str):
        """Decorator to register a method handler."""

        def decorator(func: Callable[..., Awaitable[Any]]):
            self.register(name, func)
            return func

        return decorator

    async def dispatch(self, request_data: bytes) -> bytes:
        """Dispatch a JSON-RPC request and return response bytes."""
        try:
            request = json.loads(request_data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return self._error_response(None, PARSE_ERROR, f"Parse error: {e}")

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not isinstance(method, str):
            return self._error_response(request_id, INVALID_REQUEST, "Invalid request: method must be string")

        handler = self._methods.get(method)
        if handler is None:
            return self._error_response(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")

        try:
            if isinstance(params, dict):
                result = await handler(**params)
            elif isinstance(params, list):
                result = await handler(*params)
            else:
                result = await handler()

            return self._success_response(request_id, result)

        except RPCError as e:
            return self._error_response(request_id, e.code, e.message, e.data)
        except TypeError as e:
            return self._error_response(request_id, INVALID_PARAMS, f"Invalid params: {e}")
        except Exception as e:
            tb = traceback.format_exc()
            return self._error_response(request_id, INTERNAL_ERROR, f"Internal error: {e}", tb)

    def _success_response(self, request_id: Any, result: Any) -> bytes:
        response = {"jsonrpc": "2.0", "result": result, "id": request_id}
        return json.dumps(response).encode() + b"\n"

    def _error_response(self, request_id: Any, code: int, message: str, data: Any = None) -> bytes:
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        response = {"jsonrpc": "2.0", "error": error, "id": request_id}
        return json.dumps(response).encode() + b"\n"
