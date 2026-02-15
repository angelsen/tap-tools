"""Daemon server lifecycle management.

PUBLIC API:
  - run_daemon_server: Run daemon server in foreground (blocking)
"""

import asyncio
import logging

import uvicorn
from fastapi.responses import PlainTextResponse

from webtap.api.app import api
from webtap.api.sse import broadcast_processor, get_broadcast_queue, set_broadcast_ready_event, router as sse_router
from webtap.services.daemon_state import DaemonState
from webtap.rpc import RPCFramework
from webtap.rpc.handlers import register_handlers

__all__ = ["run_daemon_server"]

logger = logging.getLogger(__name__)


def _format_controls(target: str, title: str, controls: dict) -> str:
    """Format a target's controls as plain text for LLM context.

    Args:
        target: Target ID (e.g., "9222:abc123")
        title: Page title
        controls: Output of window.controls.describeAll()

    Returns:
        Formatted text section for this target
    """
    lines = [f"  [{target} — {title}]"]
    for name, desc in controls.items():
        state = desc.get("state", "")
        lines.append(f"    {name} — {state}")
        for action_name, action in desc.get("actions", {}).items():
            action_desc = action.get("description", "")
            params = action.get("params", {})
            param_names = list(params.get("properties", {}).keys()) if isinstance(params, dict) else []
            args_str = ", ".join(param_names)
            js_call = f"controls.invoke('{name}', '{action_name}'"
            if args_str:
                js_call += ", {" + ", ".join(f"{p}: ..." for p in param_names) + "}"
            js_call += ")"
            lines.append(f'      js("{js_call}", "{target}")  {action_desc}')
        for prop_name, prop in desc.get("properties", {}).items():
            prop_desc = prop.get("description", "")
            value = prop.get("value")
            val_str = f" → {value}" if value is not None else ""
            lines.append(f"      {name}.{prop_name}{val_str}  {prop_desc}")
    lines.append("")
    return "\n".join(lines)


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

    @api.get("/prompt", response_class=PlainTextResponse)
    async def get_prompt() -> str:
        """Aggregate window.controls from all connected targets.

        Sweeps watched targets for controls registries, formats their
        descriptions as plain text for LLM context injection.
        """
        if not app_module.app_state:
            return ""

        service = app_module.app_state.service
        targets = service.get_tracked_or_all()
        if not targets:
            return ""

        sections: list[str] = []
        for tid in targets:
            conn = service.connections.get(tid)
            if not conn:
                continue
            try:
                result = conn.cdp.execute(
                    "Runtime.evaluate",
                    {
                        "expression": "window.controls?.describeAll()",
                        "returnByValue": True,
                        "awaitPromise": False,
                    },
                    timeout=2.0,
                )
                value = result.get("result", {}).get("value")
                if not value:
                    continue
                title = conn.page_info.get("title", tid)
                sections.append(_format_controls(tid, title, value))
            except Exception:
                continue

        if not sections:
            return ""

        lines = [f"Active controls ({len(sections)} target{'s' if len(sections) != 1 else ''}):", ""]
        lines.extend(sections)
        lines.append("Tip: Actions emit observations to console. Use console() to verify results.")
        return "\n".join(lines)

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
