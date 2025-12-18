"""RPC framework for JSON-RPC 2.0 request handling.

PUBLIC API:
  - RPCFramework: Core RPC request/response handler with method registration
  - RPCContext: Context passed to RPC handlers
  - HandlerMeta: Metadata for RPC handler registration
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from webtap.rpc.errors import ErrorCode, RPCError

if TYPE_CHECKING:
    from webtap.rpc.machine import ConnectionMachine
    from webtap.services.main import WebTapService

logger = logging.getLogger(__name__)


@dataclass
class RPCContext:
    """Context passed to RPC handlers.

    Attributes:
        service: WebTapService instance for accessing CDP and domain services
        machine: ConnectionMachine for state management
        epoch: Current connection epoch
        request_id: JSON-RPC request ID
    """

    service: "WebTapService"
    machine: "ConnectionMachine"
    epoch: int
    request_id: str


@dataclass
class HandlerMeta:
    """Metadata for RPC handler registration.

    Attributes:
        requires_state: List of valid connection states for this handler
    """

    requires_state: list[str]


class RPCFramework:
    """JSON-RPC 2.0 framework with state machine integration."""

    def __init__(self, service: "WebTapService"):
        self.service = service
        from webtap.rpc.machine import ConnectionMachine

        self.machine = ConnectionMachine()
        self.handlers: dict[str, tuple[Callable, HandlerMeta]] = {}

    def method(self, name: str, requires_state: list[str] | None = None) -> Callable:
        """Decorator to register RPC method handlers.

        Args:
            name: RPC method name (e.g., "connect", "browser.startInspect")
            requires_state: List of valid states for this method (e.g., ["connected"])

        Example:
            @rpc.method("connect")
            def connect(ctx: RPCContext, page_id: str = None) -> dict:
                return {"connected": True}
        """

        def decorator(func: Callable) -> Callable:
            meta = HandlerMeta(requires_state=requires_state or [])
            self.handlers[name] = (func, meta)
            return func

        return decorator

    async def handle(self, request: dict) -> dict:
        """Handle JSON-RPC 2.0 request.

        Args:
            request: JSON-RPC 2.0 request dict

        Returns:
            JSON-RPC 2.0 response dict
        """
        request_id = request.get("id", "")

        try:
            # Validate JSON-RPC 2.0 format
            if request.get("jsonrpc") != "2.0":
                return self._error_response(request_id, ErrorCode.INVALID_PARAMS, "Invalid JSON-RPC version")

            method = request.get("method")
            if not method:
                return self._error_response(request_id, ErrorCode.INVALID_PARAMS, "Missing method")

            params = request.get("params", {})

            # Find handler
            if method not in self.handlers:
                return self._error_response(request_id, ErrorCode.METHOD_NOT_FOUND, f"Unknown method: {method}")

            handler, meta = self.handlers[method]

            # Validate state requirements
            current_state = self.machine.state
            if meta.requires_state and current_state not in meta.requires_state:
                return self._error_response(
                    request_id,
                    ErrorCode.INVALID_STATE,
                    f"Method {method} requires state {meta.requires_state}, current: {current_state}",
                    {"current_state": current_state, "required_states": meta.requires_state},
                )

            # Validate epoch (if provided)
            request_epoch = request.get("epoch")
            if request_epoch is not None and request_epoch != self.machine.epoch:
                return self._error_response(
                    request_id,
                    ErrorCode.STALE_EPOCH,
                    f"Request epoch {request_epoch} does not match current {self.machine.epoch}",
                    {"request_epoch": request_epoch, "current_epoch": self.machine.epoch},
                )

            # Create context
            ctx = RPCContext(
                service=self.service, machine=self.machine, epoch=self.machine.epoch, request_id=request_id
            )

            # Execute handler in thread pool (service methods are sync)
            try:
                result = await asyncio.to_thread(handler, ctx, **params)
                return self._success_response(request_id, result)
            except RPCError as e:
                return self._error_response(request_id, e.code, e.message, e.data)
            except TypeError as e:
                # Parameter mismatch (missing/extra params)
                return self._error_response(request_id, ErrorCode.INVALID_PARAMS, f"Invalid parameters: {e}")
            except Exception as e:
                logger.exception(f"RPC handler error: {method}")
                return self._error_response(request_id, ErrorCode.INTERNAL_ERROR, str(e))

        except Exception as e:
            logger.exception("RPC request processing error")
            return self._error_response(request_id, ErrorCode.INTERNAL_ERROR, str(e))

    def _success_response(self, request_id: str, result: Any) -> dict:
        """Build JSON-RPC 2.0 success response."""
        return {"jsonrpc": "2.0", "id": request_id, "result": result, "epoch": self.machine.epoch}

    def _error_response(self, request_id: str, code: str, message: str, data: dict | None = None) -> dict:
        """Build JSON-RPC 2.0 error response."""
        error: dict[str, Any] = {"code": code, "message": message}
        if data:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error, "epoch": self.machine.epoch}
