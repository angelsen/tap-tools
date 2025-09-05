"""FastAPI endpoints for WebTap browser extension.

PUBLIC API:
  - start_api_server: Start API server in background thread
"""

import logging
import os
import socket
import threading
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn


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
app_state = None


@api.get("/pages")
async def list_pages() -> Dict[str, Any]:
    """List available Chrome pages for extension selection."""
    if not app_state:
        return {"error": "WebTap not initialized", "pages": []}

    return app_state.service.list_pages()


@api.get("/status")
async def get_status() -> Dict[str, Any]:
    """Get current connection status and event count."""
    if not app_state:
        return {"connected": False, "error": "WebTap not initialized", "events": 0}

    return app_state.service.get_status()


@api.post("/connect")
async def connect(request: ConnectRequest) -> Dict[str, Any]:
    """Connect to a Chrome page by stable page ID."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    return app_state.service.connect_to_page(page_id=request.page_id)


@api.post("/disconnect")
async def disconnect() -> Dict[str, Any]:
    """Disconnect from currently connected page."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    return app_state.service.disconnect()


@api.post("/clear")
async def clear_events() -> Dict[str, Any]:
    """Clear all stored events from DuckDB."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    return app_state.service.clear_events()


@api.post("/fetch")
async def set_fetch_interception(request: FetchRequest) -> Dict[str, Any]:
    """Enable or disable fetch request interception."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    if request.enabled:
        result = app_state.service.fetch.enable(app_state.service.cdp, response_stage=request.response_stage)
    else:
        result = app_state.service.fetch.disable()
    return result


@api.get("/fetch/paused")
async def get_paused_requests() -> Dict[str, Any]:
    """Get list of currently paused fetch requests."""
    if not app_state:
        return {"error": "WebTap not initialized", "requests": []}

    fetch_service = app_state.service.fetch
    if not fetch_service.enabled:
        return {"enabled": False, "requests": []}

    paused_list = fetch_service.get_paused_list()
    return {
        "enabled": True,
        "requests": paused_list,
        "count": len(paused_list),
        "response_stage": fetch_service.enable_response_stage,
    }


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

    return {"category": category, "enabled": enabled, "total_enabled": len(fm.enabled_categories)}


@api.post("/filters/enable-all")
async def enable_all_filters() -> Dict[str, Any]:
    """Enable all available filter categories."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    fm = app_state.service.filters
    fm.set_enabled_categories(None)
    fm.save()

    return {"enabled": list(fm.enabled_categories), "total": len(fm.enabled_categories)}


@api.post("/filters/disable-all")
async def disable_all_filters() -> Dict[str, Any]:
    """Disable all filter categories."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    fm = app_state.service.filters
    fm.set_enabled_categories([])
    fm.save()

    return {"enabled": [], "total": 0}


@api.get("/instance")
async def get_instance_info() -> Dict[str, Any]:
    """Get info about this WebTap instance."""
    if not app_state:
        return {"error": "WebTap not initialized"}

    return {
        "pid": os.getpid(),
        "connected_to": app_state.cdp.current_page_title if app_state.cdp.is_connected else None,
        "events": app_state.cdp.event_count,
    }


@api.post("/release")
async def release_port() -> Dict[str, Any]:
    """Release API port for another WebTap instance."""
    logger.info("Releasing API port for another instance")

    # Schedule graceful shutdown after response
    def shutdown():
        # Just set the flag to stop uvicorn, don't kill the whole process
        global _shutdown_requested
        _shutdown_requested = True

    threading.Timer(0.5, shutdown).start()
    return {"message": "Releasing port 8765"}


# Flag to signal shutdown
_shutdown_requested = False


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
    try:
        with socket.socket() as s:
            s.bind((host, port))
    except OSError:
        logger.info(f"Port {port} already in use")
        return None

    global app_state
    app_state = state

    thread = threading.Thread(target=run_server, args=(host, port), daemon=True)
    thread.start()

    logger.info(f"API server started on http://{host}:{port}")
    return thread


def run_server(host: str, port: int):
    """Run the FastAPI server in a thread."""
    try:
        config = uvicorn.Config(
            api,
            host=host,
            port=port,
            log_level="error",
            access_log=False,
        )
        server = uvicorn.Server(config)

        # Run with checking for shutdown flag
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def serve():
            await server.serve()

        # Start serving
        task = loop.create_task(serve())

        # Check for shutdown flag
        while not _shutdown_requested:
            loop.run_until_complete(asyncio.sleep(0.1))
            if task.done():
                break

        # Shutdown if requested
        if _shutdown_requested:
            logger.info("API server shutting down")
            server.should_exit = True
            loop.run_until_complete(server.shutdown())

    except Exception as e:
        logger.error(f"API server failed: {e}")


__all__ = ["start_api_server"]
