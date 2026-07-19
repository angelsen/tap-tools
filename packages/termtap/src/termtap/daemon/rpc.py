"""JSON-RPC 2.0 dispatcher for termtap daemon.

PUBLIC API:
  - RPCDispatcher: Register and dispatch JSON-RPC methods
"""

import inspect
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
        self._methods: dict[str, tuple[Callable[..., Awaitable[Any]], inspect.Signature]] = {}

    def register(self, name: str, handler: Callable[..., Awaitable[Any]]):
        """Register an async method handler (signature cached for param binding)."""
        self._methods[name] = (handler, inspect.signature(handler))

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

        if not isinstance(request, dict):
            return encode(error_response(None, INVALID_REQUEST, "Invalid request: expected JSON object"))

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not isinstance(method, str):
            return encode(error_response(request_id, INVALID_REQUEST, "Invalid request: method must be string"))

        entry = self._methods.get(method)
        if entry is None:
            return encode(error_response(request_id, METHOD_NOT_FOUND, f"Method not found: {method}"))
        handler, sig = entry

        # Bind params separately so only true signature mismatches map to
        # INVALID_PARAMS; a TypeError raised inside the handler body is an
        # internal error and must keep its traceback.
        try:
            if isinstance(params, dict):
                bound = sig.bind(**params)
            elif isinstance(params, list):
                bound = sig.bind(*params)
            else:
                bound = sig.bind()
        except TypeError as e:
            return encode(error_response(request_id, INVALID_PARAMS, f"Invalid params: {e}"))

        try:
            result = await handler(*bound.args, **bound.kwargs)
            return encode(success_response(request_id, result))

        except RPCError as e:
            return encode(error_response(request_id, e.code, e.message, e.data))
        except Exception as e:
            tb = traceback.format_exc()
            return encode(error_response(request_id, INTERNAL_ERROR, f"Internal error: {e}", tb))
