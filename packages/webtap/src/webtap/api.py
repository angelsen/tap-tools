"""FastAPI endpoints for WebTap browser extension.

PUBLIC API:
  - start_api_server: Start API server in background thread
"""

import asyncio
import logging
import os
import socket
import threading
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import json as json_module


logger = logging.getLogger(__name__)


# Request models
class ConnectRequest(BaseModel):
    """Request model for connecting to a Chrome page."""

    page_id: str


class FetchRequest(BaseModel):
    """Request model for enabling/disabling fetch interception."""

    enabled: bool
    response_stage: bool = False  # Optional: also pause at Response stage


# Create FastAPI app
api = FastAPI(title="WebTap API", version="0.1.0")

# Enable CORS for extension
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Chrome extensions have unique origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global reference to WebTap state (set by start_api_server)
app_state: "Any | None" = None

# SSE clients - set of queues for broadcasting state
_sse_clients: set[asyncio.Queue] = set()
_sse_clients_lock = asyncio.Lock()

# Broadcast queue for cross-thread communication
_broadcast_queue: "asyncio.Queue[Dict[str, Any]] | None" = None


@api.get("/health")
async def health_check() -> Dict[str, Any]:
    """Quick health check endpoint for extension."""
    return {"status": "ok", "pid": os.getpid()}


@api.get("/info")
async def get_info() -> Dict[str, Any]:
    """Combined endpoint for pages and instance info - reduces round trips."""
    if not app_state:
        return {"error": "WebTap not initialized", "pages": [], "pid": os.getpid()}

    # Get pages - wrap blocking HTTP call in thread
    pages_data = await asyncio.to_thread(app_state.service.list_pages)

    # Get instance info
    connected_to = None
    if app_state.cdp.is_connected and app_state.cdp.page_info:
        connected_to = app_state.cdp.page_info.get("title", "Untitled")

    return {
        "pid": os.getpid(),
        "connected_to": connected_to,
        "events": app_state.service.event_count,
        "pages": pages_data.get("pages", []),
        "error": pages_data.get("error"),
    }


@api.get("/status")
async def get_status() -> Dict[str, Any]:
    """Get comprehensive status including connection, events, and fetch details."""
    if not app_state:
        return {"connected": False, "error": "WebTap not initialized", "events": 0}

    status = app_state.service.get_status()

    # Add fetch details if fetch is enabled
    if status.get("fetch_enabled"):
        fetch_service = app_state.service.fetch
        paused_list = fetch_service.get_paused_list()
        status["fetch_details"] = {
            "paused_requests": paused_list,
            "paused_count": len(paused_list),
            "response_stage": fetch_service.enable_response_stage,
        }

    return status


@api.post("/connect")
async def connect(request: ConnectRequest) -> Dict[str, Any]:
    """Connect to a Chrome page by stable page ID."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    # Wrap blocking CDP calls (connect + enable domains) in thread
    result = await asyncio.to_thread(app_state.service.connect_to_page, page_id=request.page_id)

    return result


@api.post("/disconnect")
async def disconnect() -> Dict[str, Any]:
    """Disconnect from currently connected page."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    # Wrap blocking CDP calls (fetch.disable + disconnect) in thread
    result = await asyncio.to_thread(app_state.service.disconnect)

    return result


@api.post("/clear")
async def clear_events() -> Dict[str, Any]:
    """Clear all stored events from DuckDB."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    # Wrap blocking DB operation in thread
    result = await asyncio.to_thread(app_state.service.clear_events)

    return result


@api.post("/fetch")
async def set_fetch_interception(request: FetchRequest) -> Dict[str, Any]:
    """Enable or disable fetch request interception."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    # Wrap blocking CDP calls (Fetch.enable/disable) in thread
    if request.enabled:
        result = await asyncio.to_thread(
            app_state.service.fetch.enable, app_state.service.cdp, response_stage=request.response_stage
        )
    else:
        result = await asyncio.to_thread(app_state.service.fetch.disable)

    # Broadcast state change
    app_state.service._trigger_broadcast()

    return result


@api.get("/filters/status")
async def get_filter_status() -> Dict[str, Any]:
    """Get current filter configuration and enabled categories."""
    if not app_state:
        return {"error": "WebTap not initialized", "filters": {}, "enabled": []}

    fm = app_state.service.filters
    return {"filters": fm.filters, "enabled": list(fm.enabled_categories), "path": str(fm.filter_path)}


@api.post("/filters/toggle/{category}")
async def toggle_filter_category(category: str) -> Dict[str, Any]:
    """Toggle a specific filter category on or off."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    fm = app_state.service.filters

    if category not in fm.filters:
        return {"error": f"Category '{category}' not found"}

    if category in fm.enabled_categories:
        fm.enabled_categories.discard(category)
        enabled = False
    else:
        fm.enabled_categories.add(category)
        enabled = True

    fm.save()

    # Broadcast state change
    app_state.service._trigger_broadcast()

    return {"category": category, "enabled": enabled, "total_enabled": len(fm.enabled_categories)}


@api.post("/filters/enable-all")
async def enable_all_filters() -> Dict[str, Any]:
    """Enable all available filter categories."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    fm = app_state.service.filters
    fm.set_enabled_categories(None)
    fm.save()

    # Broadcast state change
    app_state.service._trigger_broadcast()

    return {"enabled": list(fm.enabled_categories), "total": len(fm.enabled_categories)}


@api.post("/filters/disable-all")
async def disable_all_filters() -> Dict[str, Any]:
    """Disable all filter categories."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    fm = app_state.service.filters
    fm.set_enabled_categories([])
    fm.save()

    # Broadcast state change
    app_state.service._trigger_broadcast()

    return {"enabled": [], "total": 0}


@api.post("/browser/start-inspect")
async def start_inspect() -> Dict[str, Any]:
    """Enable CDP element inspection mode."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    if not app_state.cdp.is_connected:
        return {"error": "Not connected to a page"}

    # Wrap blocking CDP calls (DOM.enable, CSS.enable, Overlay.enable, setInspectMode) in thread
    result = await asyncio.to_thread(app_state.service.dom.start_inspect)

    return result


@api.post("/browser/stop-inspect")
async def stop_inspect() -> Dict[str, Any]:
    """Disable CDP element inspection mode."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    # Wrap blocking CDP call (Overlay.setInspectMode) in thread
    result = await asyncio.to_thread(app_state.service.dom.stop_inspect)

    return result


@api.post("/browser/clear")
async def clear_selections() -> Dict[str, Any]:
    """Clear all element selections."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    app_state.service.dom.clear_selections()

    return {"success": True, "selections": {}}


@api.post("/errors/dismiss")
async def dismiss_error() -> Dict[str, Any]:
    """Dismiss the current error."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    app_state.error_state = None

    # Broadcast state change
    app_state.service._trigger_broadcast()

    return {"success": True}


# Removed /browser/prompt endpoint - selections now accessed via @webtap:webtap://selections resource
# Selections are captured via CDP in DOMService, no submit flow needed


@api.get("/events")
async def stream_events():
    """Server-Sent Events stream for real-time WebTap state updates.

    Streams full state object on every change. Extension receives:
    - Connection status
    - Event counts
    - Fetch interception status
    - Filter status
    - Element selection state (inspect_active, selections)

    Returns:
        StreamingResponse with text/event-stream content type
    """

    async def event_generator():
        """Generate SSE events with full state."""
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)

        async with _sse_clients_lock:
            _sse_clients.add(queue)

        try:
            # Send initial state on connect
            initial_state = get_full_state()
            yield f"data: {json_module.dumps(initial_state)}\n\n"

            # Stream state updates with keepalive
            while True:
                try:
                    state = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if state is None:  # Shutdown signal
                        break
                    yield f"data: {json_module.dumps(state)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"

        except asyncio.CancelledError:
            # Expected during shutdown
            pass
        except Exception as e:
            logger.debug(f"SSE stream error: {e}")
        finally:
            async with _sse_clients_lock:
                _sse_clients.discard(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        },
    )


def get_full_state() -> Dict[str, Any]:
    """Get complete WebTap state for broadcasting.

    Thread-safe, zero-lock reads from immutable snapshot.
    No blocking I/O - returns cached snapshot immediately.

    Returns:
        Dictionary with all state information for SSE clients
    """
    if not app_state:
        return {
            "connected": False,
            "events": {"total": 0},
            "fetch": {"enabled": False, "paused_count": 0},
            "filters": {"enabled": [], "disabled": []},
            "browser": {"inspect_active": False, "selections": {}, "prompt": "", "pending_count": 0},
            "error": None,
        }

    # Get immutable snapshot (NO LOCKS NEEDED - inherently thread-safe)
    snapshot = app_state.service.get_state_snapshot()

    # Convert snapshot to frontend format
    return {
        "connected": snapshot.connected,
        "page": {
            "id": snapshot.page_id,
            "title": snapshot.page_title,
            "url": snapshot.page_url,
        }
        if snapshot.connected
        else None,
        "events": {"total": snapshot.event_count},
        "fetch": {"enabled": snapshot.fetch_enabled, "paused_count": snapshot.paused_count},
        "filters": {"enabled": list(snapshot.enabled_filters), "disabled": list(snapshot.disabled_filters)},
        "browser": {
            "inspect_active": snapshot.inspect_active,
            "selections": snapshot.selections,
            "prompt": snapshot.prompt,
            "pending_count": snapshot.pending_count,
        },
        "error": {"message": snapshot.error_message, "timestamp": snapshot.error_timestamp}
        if snapshot.error_message
        else None,
    }


async def broadcast_state():
    """Broadcast current state to all SSE clients."""
    global _sse_clients

    async with _sse_clients_lock:
        if not _sse_clients:
            return
        clients = list(_sse_clients)

    state = get_full_state()
    dead_queues = set()

    # Send to all connected clients
    for queue in clients:
        try:
            queue.put_nowait(state)
        except asyncio.QueueFull:
            # Client is falling behind - discard oldest state and retry with latest
            logger.warning(f"SSE client queue full ({queue.qsize()}/{queue.maxsize}), discarding oldest state")
            try:
                queue.get_nowait()  # Discard oldest
                queue.put_nowait(state)  # Retry with latest
            except Exception as retry_err:
                logger.debug(f"Failed to recover full queue: {retry_err}")
                dead_queues.add(queue)
        except Exception as e:
            logger.debug(f"Failed to broadcast to client: {e}")
            dead_queues.add(queue)

    # Remove dead queues
    if dead_queues:
        async with _sse_clients_lock:
            _sse_clients -= dead_queues


async def broadcast_processor():
    """Background task that processes broadcast queue.

    This runs in the FastAPI event loop and watches for signals
    from WebSocket thread (via asyncio.Queue).
    """
    global _broadcast_queue
    _broadcast_queue = asyncio.Queue()
    _queue_ready.set()  # Signal that queue is ready

    logger.info("Broadcast processor started")

    while not _shutdown_requested:
        try:
            # Wait for broadcast signal (with timeout for shutdown check)
            signal = await asyncio.wait_for(_broadcast_queue.get(), timeout=1.0)
            logger.debug(f"Broadcast signal received: {signal}")

            # Broadcast to all SSE clients
            await broadcast_state()
        except asyncio.TimeoutError:
            # Normal timeout, continue loop
            continue
        except Exception as e:
            logger.error(f"Error in broadcast processor: {e}")

    # Graceful shutdown: close all SSE clients
    async with _sse_clients_lock:
        for queue in list(_sse_clients):
            try:
                queue.put_nowait(None)  # Non-blocking shutdown signal
            except asyncio.QueueFull:
                pass  # Client is hung, skip
            except Exception:
                pass
        _sse_clients.clear()

    logger.info("Broadcast processor stopped")


# Flag to signal shutdown
_shutdown_requested = False

# Event to signal broadcast queue is ready
_queue_ready = threading.Event()


def start_api_server(state, host: str = "127.0.0.1", port: int = 8765) -> threading.Thread | None:
    """Start the API server in a background thread.

    Args:
        state: WebTapState instance from the main app.
        host: Host to bind to. Defaults to 127.0.0.1.
        port: Port to bind to. Defaults to 8765.

    Returns:
        Thread instance running the server, or None if port is in use.
    """
    # Check port availability first
    # Use SO_REUSEADDR to properly test availability even if port in TIME_WAIT
    try:
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
    except OSError:
        logger.info(f"Port {port} already in use")
        return None

    global app_state, _shutdown_requested, _broadcast_queue
    app_state = state
    _shutdown_requested = False  # Reset flag for new instance
    _queue_ready.clear()  # Reset event for new instance

    # Use daemon thread so REPL can exit immediately
    # Graceful shutdown handled by atexit → cleanup() → _shutdown_requested
    thread = threading.Thread(target=run_server, args=(host, port), daemon=True, name="webtap-api")
    thread.start()

    # Wait for broadcast queue to be ready (with timeout)
    if not _queue_ready.wait(timeout=2.0):
        logger.error("Broadcast queue initialization timed out")
        return thread

    # Wire queue to service and CDP session after event loop starts
    # Note: DOMService uses callback to service._trigger_broadcast instead of direct queue access
    if _broadcast_queue and app_state:
        app_state.service.set_broadcast_queue(_broadcast_queue)
        app_state.cdp.set_broadcast_queue(_broadcast_queue)
        logger.info("Broadcast queue wired to WebTapService and CDPSession")

    logger.info(f"API server started on http://{host}:{port}")
    return thread


def run_server(host: str, port: int):
    """Run the FastAPI server in a thread."""
    import asyncio

    async def run():
        """Run server with proper shutdown handling."""
        config = uvicorn.Config(
            api,
            host=host,
            port=port,
            log_level="error",
            access_log=False,
        )
        server = uvicorn.Server(config)

        # Start server in background task
        serve_task = asyncio.create_task(server.serve())

        # Start broadcast processor in background
        broadcast_task = asyncio.create_task(broadcast_processor())

        # Wait for shutdown signal
        while not _shutdown_requested:
            await asyncio.sleep(0.1)
            if serve_task.done():
                break

        # Trigger shutdown
        if not serve_task.done():
            logger.info("API server shutting down")
            server.should_exit = True
            # Wait a bit for graceful shutdown
            try:
                await asyncio.wait_for(serve_task, timeout=1.0)
            except asyncio.TimeoutError:
                logger.debug("Server task timeout - cancelling")
                serve_task.cancel()
                try:
                    await serve_task
                except asyncio.CancelledError:
                    pass

        # Cancel broadcast processor
        if not broadcast_task.done():
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass

    try:
        # Use asyncio.run() which properly cleans up
        asyncio.run(run())
    except Exception as e:
        logger.error(f"API server failed: {e}")


__all__ = ["start_api_server"]
