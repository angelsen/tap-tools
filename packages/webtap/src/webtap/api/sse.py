"""SSE streaming and broadcast management."""

import asyncio
import json as json_module
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

import webtap.api.app as app_module
from webtap.api.state import get_full_state

logger = logging.getLogger(__name__)

SSE_SHUTDOWN_TIMEOUT = 2.0  # Max seconds to wait for SSE clients to disconnect

router = APIRouter()

# SSE client management
_sse_clients: set[asyncio.Queue] = set()
_sse_clients_lock = asyncio.Lock()
_broadcast_queue: asyncio.Queue[Dict[str, Any]] | None = None
_broadcast_ready_event: asyncio.Event | None = None


def set_broadcast_ready_event(event: asyncio.Event) -> None:
    """Set ready event signal for broadcast processor.

    Args:
        event: Event to signal when processor is ready
    """
    global _broadcast_ready_event
    _broadcast_ready_event = event


@router.get("/events/stream")
async def stream_events():
    """Server-Sent Events stream for real-time WebTap state updates.

    Streams full state object on every change. Extension receives:
    - Connection status
    - Event counts
    - Fetch interception status
    - Filter status
    - Element selection state (inspect_active, selections)

    On connect, clears notices with clear_on="extension_connect".

    Returns:
        StreamingResponse with text/event-stream content type
    """
    # Clear extension-related notices on connect
    if app_module.app_state and app_module.app_state.service:
        app_module.app_state.service.notices.clear_on_event("extension_connect")
        logger.debug("Cleared extension_connect notices on SSE connect")

    async def _event_generator():
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
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        },
    )


async def _broadcast_state():
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

    # Signal that processor is ready
    if _broadcast_ready_event:
        _broadcast_ready_event.set()

    logger.debug("Broadcast processor started")

    try:
        while True:
            try:
                # Wait for broadcast signal (with timeout for keepalive)
                signal = await asyncio.wait_for(_broadcast_queue.get(), timeout=1.0)
                logger.debug(f"Broadcast signal received: {signal}")

                # Broadcast to all SSE clients
                await _broadcast_state()

                # Clear pending flag to allow next broadcast (service owns coalescing)
                if app_module.app_state and app_module.app_state.service:
                    app_module.app_state.service.clear_broadcast_pending()
            except asyncio.TimeoutError:
                continue  # Normal timeout, continue loop
            except asyncio.CancelledError:
                raise  # Propagate cancellation
            except Exception as e:
                logger.error(f"Error in broadcast processor: {e}")
    finally:
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

        logger.debug("Broadcast processor stopped")


def get_broadcast_queue() -> asyncio.Queue | None:
    """Get broadcast queue for wiring to service."""
    return _broadcast_queue


async def shutdown_sse_clients(timeout: float = SSE_SHUTDOWN_TIMEOUT) -> None:
    """Gracefully close all SSE connections with timeout.

    Sends shutdown signal to all clients and waits for them to disconnect.
    Force-clears any remaining clients after timeout.

    Args:
        timeout: Maximum seconds to wait for clients to disconnect. Defaults to 2.0.
    """
    async with _sse_clients_lock:
        clients = list(_sse_clients)

    if not clients:
        return

    logger.debug(f"Shutting down {len(clients)} SSE clients (timeout={timeout}s)")

    # Send shutdown signal to all clients
    for queue in clients:
        try:
            queue.put_nowait(None)  # None signals shutdown
        except asyncio.QueueFull:
            pass  # Client is hung, will be force-cleared

    # Wait for clients to disconnect (with timeout)
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        async with _sse_clients_lock:
            if not _sse_clients:
                logger.debug("All SSE clients disconnected gracefully")
                return
        await asyncio.sleep(0.1)

    # Force clear any remaining clients
    async with _sse_clients_lock:
        remaining = len(_sse_clients)
        if remaining:
            logger.warning(f"Force-clearing {remaining} hung SSE clients after {timeout}s timeout")
        _sse_clients.clear()
