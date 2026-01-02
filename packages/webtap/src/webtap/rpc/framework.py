"""RPC framework for JSON-RPC 2.0 request handling.

PUBLIC API:
  - RPCFramework: Core RPC request/response handler
  - RPCContext: Context passed to RPC handlers
  - HandlerMeta: Metadata for RPC handler registration
"""

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from webtap.rpc.errors import ErrorCode, RPCError
from webtap.services.main import WebTapService

__all__ = ["RPCFramework", "RPCContext", "HandlerMeta"]

logger = logging.getLogger(__name__)


@dataclass
class RPCContext:
    """Context passed to RPC handlers.

    Attributes:
        service: WebTapService instance for accessing CDP and domain services
        epoch: Current connection epoch
        request_id: JSON-RPC request ID
    """

    service: WebTapService
    epoch: int
    request_id: str


@dataclass
class HandlerMeta:
    """Metadata for RPC handler registration.

    Attributes:
        requires_state: List of valid connection states for this handler
        broadcasts: Whether to trigger SSE broadcast after successful execution. Defaults to True.
    """

    requires_state: list[str]
    broadcasts: bool = True


class RPCFramework:
    """JSON-RPC 2.0 framework for request routing and validation.

    Handles JSON-RPC 2.0 request routing, validation, and response formatting.
    Uses per-target state from ConnectionManager for validation.
    """

    def __init__(self, service: "WebTapService"):
        self.service = service
        self.handlers: dict[str, tuple[Callable, HandlerMeta]] = {}

        # Client tracking: {client_id: {version, type, context, last_seen, is_stale}}
        self._clients: dict[str, dict[str, Any]] = {}
        self._client_lock = asyncio.Lock()

    def method(
        self,
        name: str,
        requires_state: list[str] | None = None,
        broadcasts: bool = True,
    ) -> Callable:
        """Decorator to register RPC method handlers.

        Args:
            name: RPC method name (e.g., "connect", "browser.startInspect")
            requires_state: List of valid states for this method. Defaults to None.
            broadcasts: Whether to trigger SSE broadcast after successful execution. Defaults to True.

        Returns:
            Decorator function for handler registration.

        Example:
            @rpc.method("connect")
            def connect(ctx: RPCContext, page_id: str = None) -> dict:
                return {"connected": True}
        """

        def decorator(func: Callable) -> Callable:
            meta = HandlerMeta(
                requires_state=requires_state or [],
                broadcasts=broadcasts,
            )
            self.handlers[name] = (func, meta)
            return func

        return decorator

    async def _update_client_tracking(self, headers: dict[str, str]) -> None:
        """Update client tracking from request headers.

        Args:
            headers: HTTP headers from RPC request
        """
        version = headers.get("x-webtap-version")
        client_type = headers.get("x-webtap-client-type")
        context = headers.get("x-webtap-context")

        if not (version and client_type and context):
            return  # Not a tracked client (e.g., extension, old client)

        # Generate client ID from type + context
        client_id = hashlib.md5(f"{client_type}:{context}".encode()).hexdigest()[:16]

        # Get daemon version for staleness check
        from webtap import __version__

        is_stale = version < __version__

        async with self._client_lock:
            # Check if this is a newly detected stale client
            was_known_stale = client_id in self._clients and self._clients[client_id].get("is_stale")

            self._clients[client_id] = {
                "version": version,
                "client_type": client_type,
                "context": context,
                "last_seen": time.time(),
                "is_stale": is_stale,
            }

            # Prune stale clients (>5min since last seen)
            cutoff = time.time() - 300  # 5 minutes
            self._clients = {k: v for k, v in self._clients.items() if v["last_seen"] > cutoff}

        # Notify about stale client (only once per client)
        if is_stale and not was_known_stale:
            self.service.notices.add(
                "client_stale",
                client_type=client_type,
                version=version,
                context=context,
            )

    def get_tracked_clients(self) -> dict[str, dict[str, Any]]:
        """Get all tracked clients (thread-safe snapshot).

        Returns:
            Dict of client_id -> client info
        """
        return dict(self._clients)

    async def handle(self, request: dict, headers: dict[str, str] | None = None) -> dict:
        """Handle JSON-RPC 2.0 request.

        Validates request format, routes to handler, manages state transitions.

        Args:
            request: JSON-RPC 2.0 request dict
            headers: HTTP headers from request (for client tracking)

        Returns:
            JSON-RPC 2.0 response dict (success or error)
        """
        # Update client tracking if headers provided
        if headers:
            await self._update_client_tracking(headers)

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

            # Validate state requirements (per-target only)
            target_param = params.get("target")
            if target_param and meta.requires_state:
                conn = self.service.get_connection(target_param)
                if conn:
                    target_state = conn.state.value
                    if target_state not in meta.requires_state:
                        return self._error_response(
                            request_id,
                            ErrorCode.INVALID_STATE,
                            f"Target {target_param} in state {target_state}, requires {meta.requires_state}",
                            {
                                "target": target_param,
                                "current_state": target_state,
                                "required_states": meta.requires_state,
                            },
                        )
            elif meta.requires_state:
                # No target param but requires state - check if any connection exists
                if not self.service.connections:
                    return self._error_response(
                        request_id,
                        ErrorCode.NOT_CONNECTED,
                        f"Method {method} requires connection",
                        {"required_states": meta.requires_state},
                    )

            # Get current epoch from service
            current_epoch = self.service.conn_mgr.epoch

            # Validate epoch (if provided)
            request_epoch = request.get("epoch")
            if request_epoch is not None and request_epoch != current_epoch:
                return self._error_response(
                    request_id,
                    ErrorCode.STALE_EPOCH,
                    f"Request epoch {request_epoch} does not match current {current_epoch}",
                    {"request_epoch": request_epoch, "current_epoch": current_epoch},
                )

            # Create context
            ctx = RPCContext(service=self.service, epoch=current_epoch, request_id=request_id)

            # Execute handler in thread pool (service methods are sync)
            try:
                result = await asyncio.to_thread(handler, ctx, **params)

                # Auto-broadcast for state-modifying handlers
                if meta.broadcasts:
                    self.service._trigger_broadcast()

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
        """Build JSON-RPC 2.0 success response.

        Args:
            request_id: JSON-RPC request ID
            result: Result data to return
        """
        return {"jsonrpc": "2.0", "id": request_id, "result": result, "epoch": self.service.conn_mgr.epoch}

    def _error_response(self, request_id: str, code: str, message: str, data: dict | None = None) -> dict:
        """Build JSON-RPC 2.0 error response.

        Args:
            request_id: JSON-RPC request ID
            code: Error code
            message: Error message
            data: Optional error data
        """
        error: dict[str, Any] = {"code": code, "message": message}
        if data:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error, "epoch": self.service.conn_mgr.epoch}
