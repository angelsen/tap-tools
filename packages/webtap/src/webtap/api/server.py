"""Daemon server lifecycle management."""

import asyncio
import logging

import uvicorn

from webtap.api.app import api
from webtap.api.sse import broadcast_processor, get_broadcast_queue, set_broadcast_ready_event, router as sse_router
from webtap.daemon_state import DaemonState
from webtap.rpc import RPCFramework
from webtap.rpc.handlers import register_handlers

logger = logging.getLogger(__name__)


def run_daemon_server(host: str = "127.0.0.1", port: int = 8765):
    """Run daemon server in foreground (blocking).

    This function is called by daemon.py when running in --daemon mode.
    It initializes daemon state with CDPSession and WebTapService,
    then runs the API server.

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    import os
    import webtap.api.app as app_module
    from fastapi import Request

    # Initialize daemon state
    app_module.app_state = DaemonState()
    logger.info("Daemon initialized with CDPSession and WebTapService")

    # Initialize RPC framework and register handlers
    rpc = RPCFramework(app_module.app_state.service)
    register_handlers(rpc)
    app_module.app_state.service.rpc = rpc
    logger.info("RPC framework initialized with 22 handlers")

    # Add single RPC endpoint
    @api.post("/rpc")
    async def handle_rpc(request: Request) -> dict:
        """Handle JSON-RPC 2.0 requests."""
        body = await request.json()
        return await rpc.handle(body)

    # Add health check endpoint
    @api.get("/health")
    async def health_check() -> dict:
        """Quick health check endpoint for extension."""
        return {"status": "ok", "pid": os.getpid()}

    # Include SSE endpoint
    api.include_router(sse_router)

    async def run():
        """Run server with proper shutdown handling."""
        config = uvicorn.Config(
            api,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)

        # Create event for broadcast processor ready signal
        ready_event = asyncio.Event()
        set_broadcast_ready_event(ready_event)

        # Start broadcast processor in background
        broadcast_task = asyncio.create_task(broadcast_processor())

        # Wait for processor to be ready (with timeout)
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error("Broadcast processor failed to start")
            broadcast_task.cancel()
            return

        # Wire broadcast queue to service
        queue = get_broadcast_queue()
        if queue and app_module.app_state:
            app_module.app_state.service.set_broadcast_queue(queue)
            logger.debug("Broadcast queue wired to WebTapService")

        try:
            await server.serve()
        except (SystemExit, KeyboardInterrupt):
            pass
        finally:
            if not broadcast_task.done():
                broadcast_task.cancel()
                try:
                    await broadcast_task
                except asyncio.CancelledError:
                    pass

    try:
        asyncio.run(run())
    except (SystemExit, KeyboardInterrupt):
        pass
    except Exception as e:
        logger.error(f"Daemon server failed: {e}")
    finally:
        if app_module.app_state:
            app_module.app_state.cleanup()
        logger.info("Daemon cleanup complete")
