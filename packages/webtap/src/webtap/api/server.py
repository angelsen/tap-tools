"""Daemon server lifecycle management.

PUBLIC API:
  - run_daemon_server: Run daemon server in foreground (blocking)
"""

import asyncio
import logging

import uvicorn

from webtap.api.app import api
from webtap.api.sse import broadcast_processor, get_broadcast_queue, set_broadcast_ready_event, router as sse_router
from webtap.services.daemon_state import DaemonState
from webtap.rpc import RPCFramework
from webtap.rpc.handlers import register_handlers

__all__ = ["run_daemon_server"]

logger = logging.getLogger(__name__)


def run_daemon_server(host: str = "127.0.0.1", port: int = 37650):
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

    # Check extension once at startup (not on every connect)
    from webtap.services.setup.extension import auto_update_extension
    from webtap.services.setup.platform import get_platform_info

    try:
        ext_status = auto_update_extension()
        # Generate notices directly instead of storing status
        if ext_status.status == "missing":
            app_module.app_state.service.notices.add(
                "extension_installed",
                path=str(get_platform_info()["paths"]["data_dir"] / "extension"),
            )
        elif ext_status.status == "manifest_changed":
            app_module.app_state.service.notices.add("extension_manifest_changed")
        elif ext_status.status == "outdated":
            app_module.app_state.service.notices.add("extension_updated")
        # dev_mode and ok: no notice needed
        logger.info(f"Extension check complete: {ext_status.status}")
    except Exception as e:
        logger.warning(f"Extension check failed: {e}")

    # Initialize RPC framework and register handlers
    rpc = RPCFramework(app_module.app_state.service)
    register_handlers(rpc)
    app_module.app_state.service.rpc = rpc
    logger.info("RPC framework initialized with 22 handlers")

    @api.post("/rpc")
    async def handle_rpc(request: Request) -> dict:
        """Handle JSON-RPC 2.0 requests.

        Args:
            request: FastAPI request object with JSON body

        Returns:
            JSON-RPC response dictionary
        """
        body = await request.json()
        headers = dict(request.headers)
        return await rpc.handle(body, headers=headers)

    @api.get("/health")
    async def health_check() -> dict:
        """Health check endpoint for extension.

        Returns:
            Dictionary with status, pid, and version
        """
        from webtap import __version__

        return {"status": "ok", "pid": os.getpid(), "version": __version__}

    # Include SSE endpoint
    api.include_router(sse_router)

    async def _run():
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

        # Start background services (Chrome watcher)
        if app_module.app_state:
            app_module.app_state.service.start()

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
        asyncio.run(_run())
    except (SystemExit, KeyboardInterrupt):
        pass
    except Exception as e:
        logger.error(f"Daemon server failed: {e}")
    finally:
        if app_module.app_state:
            app_module.app_state.cleanup()
        logger.info("Daemon cleanup complete")
