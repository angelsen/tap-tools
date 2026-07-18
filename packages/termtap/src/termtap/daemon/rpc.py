"""JSON-RPC 2.0 dispatcher for termtap daemon.

PUBLIC API:
  - RPCDispatcher: Register and dispatch JSON-RPC methods
"""

import json
import traceback
from typing import Any, Callable, Awaitable

from ..protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    RPCError,
    encode,
    error_response,
    success_response,
)

__all__ = ["RPCDispatcher"]


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
            return encode(error_response(None, PARSE_ERROR, f"Parse error: {e}"))

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not isinstance(method, str):
            return encode(error_response(request_id, INVALID_REQUEST, "Invalid request: method must be string"))

        handler = self._methods.get(method)
        if handler is None:
            return encode(error_response(request_id, METHOD_NOT_FOUND, f"Method not found: {method}"))

        try:
            if isinstance(params, dict):
                result = await handler(**params)
            elif isinstance(params, list):
                result = await handler(*params)
            else:
                result = await handler()

            return encode(success_response(request_id, result))

        except RPCError as e:
            return encode(error_response(request_id, e.code, e.message, e.data))
        except TypeError as e:
            return encode(error_response(request_id, INVALID_PARAMS, f"Invalid params: {e}"))
        except Exception as e:
            tb = traceback.format_exc()
            return encode(error_response(request_id, INTERNAL_ERROR, f"Internal error: {e}", tb))
