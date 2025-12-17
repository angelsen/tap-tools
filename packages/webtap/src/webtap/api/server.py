"""Daemon server lifecycle management.

PUBLIC API:
  - run_daemon_server: Run daemon server in foreground (blocking)
"""

import asyncio
import logging

import uvicorn

from webtap.api.app import api
from webtap.api.routes import include_routes
from webtap.api.sse import broadcast_processor, get_broadcast_queue, set_broadcast_ready_event
from webtap.daemon_state import DaemonState

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
    import webtap.api.app as app_module

    include_routes(api)

    app_module.app_state = DaemonState()
    logger.info("Daemon initialized with CDPSession and WebTapService")

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
