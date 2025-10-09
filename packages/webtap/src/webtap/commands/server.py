"""API server management command.

PUBLIC API:
  - server: Manage API server (status/start/stop/restart)
"""

import socket
import time
import logging

from webtap.app import app
from webtap.api import start_api_server

logger = logging.getLogger(__name__)

# Fixed port for API server
API_PORT = 8765


def _check_port() -> bool:
    """Check if API port is in use."""
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", API_PORT))
            return False  # Port is free
        except OSError:
            return True  # Port is in use


def _stop_server(state) -> tuple[bool, str]:
    """Stop the server if this instance owns it."""
    if not state.api_thread or not state.api_thread.is_alive():
        return False, "Not running"

    import webtap.api

    webtap.api._shutdown_requested = True
    state.api_thread.join(timeout=2.0)
    state.api_thread = None

    return True, "Server stopped"


def _start_server(state) -> tuple[bool, str]:
    """Start the server on port 8765."""
    # Check if already running
    if state.api_thread and state.api_thread.is_alive():
        return True, f"Already running on port {API_PORT}"

    # Check if port is in use
    if _check_port():
        return False, f"Port {API_PORT} already in use by another process"

    # Start the server
    thread = start_api_server(state, port=API_PORT)
    if thread:
        state.api_thread = thread

        # Register cleanup
        import atexit

        atexit.register(lambda: state.cleanup() if state else None)

        return True, f"Server started on port {API_PORT}"
    else:
        return False, "Failed to start server"


@app.command(
    display="markdown",
    fastmcp={
        "type": "prompt",
        "description": "API server control: status (default), start, stop, restart",
        "arg_descriptions": {"action": "Server action: status (default), start, stop, or restart"},
    },
)
def server(state, action: str = None) -> dict:  # pyright: ignore[reportArgumentType]
    """API server status and management information.

    Returns current server state and available actions.
    """
    if action is None:
        action = "status"

    action = action.lower()
    owns_server = bool(state.api_thread and state.api_thread.is_alive())

    # Build markdown elements based on action
    elements = []

    if action == "status" or action not in ["start", "stop", "restart"]:
        # Status information
        elements.append({"type": "heading", "content": "API Server Status", "level": 2})

        if owns_server:
            elements.append({"type": "text", "content": "**Status:** Running"})
            elements.append({"type": "text", "content": f"**Port:** {API_PORT}"})
            elements.append({"type": "text", "content": f"**URL:** http://127.0.0.1:{API_PORT}"})
            elements.append({"type": "text", "content": f"**Health:** http://127.0.0.1:{API_PORT}/health"})
            elements.append({"type": "text", "content": "**Extension:** Ready to connect"})
        else:
            port_in_use = _check_port()
            if port_in_use:
                elements.append({"type": "alert", "message": "Port 8765 in use by another process", "level": "warning"})
                elements.append({"type": "text", "content": "Cannot start server until port is free"})
            else:
                elements.append({"type": "text", "content": "**Status:** Not running"})
                elements.append({"type": "text", "content": f"**Port:** {API_PORT} (available)"})
                elements.append({"type": "text", "content": "Use `server('start')` to start the API server"})

        # Available actions
        elements.append({"type": "heading", "content": "Available Actions", "level": 3})
        actions = [
            "`server('start')` - Start the API server",
            "`server('stop')` - Stop the API server",
            "`server('restart')` - Restart the API server",
            "`server('status')` or `server()` - Show this status",
        ]
        elements.append({"type": "list", "items": actions})

    elif action == "start":
        if owns_server:
            elements.append({"type": "alert", "message": f"Server already running on port {API_PORT}", "level": "info"})
        else:
            success, message = _start_server(state)
            if success:
                elements.append({"type": "alert", "message": message, "level": "success"})
                elements.append({"type": "text", "content": f"**URL:** http://127.0.0.1:{API_PORT}"})
                elements.append({"type": "text", "content": f"**Health:** http://127.0.0.1:{API_PORT}/health"})
                elements.append({"type": "text", "content": "Chrome extension can now connect"})
            else:
                elements.append({"type": "alert", "message": message, "level": "error"})

    elif action == "stop":
        if not owns_server:
            elements.append({"type": "text", "content": "Server not running"})
        else:
            success, message = _stop_server(state)
            if success:
                elements.append({"type": "alert", "message": message, "level": "success"})
            else:
                elements.append({"type": "alert", "message": message, "level": "error"})

    elif action == "restart":
        if owns_server:
            success, msg = _stop_server(state)
            if not success:
                elements.append({"type": "alert", "message": f"Failed to stop: {msg}", "level": "error"})
                return {"elements": elements}
            time.sleep(0.5)

        success, msg = _start_server(state)
        if success:
            elements.append({"type": "alert", "message": "Server restarted", "level": "success"})
            elements.append({"type": "text", "content": f"**Port:** {API_PORT}"})
            elements.append({"type": "text", "content": f"**URL:** http://127.0.0.1:{API_PORT}"})
        else:
            elements.append({"type": "alert", "message": f"Failed to restart: {msg}", "level": "error"})

    # For MCP prompt mode, return with caveat and assistant prefill
    # This prevents LLM from adding commentary - just relays the state
    if action == "status":
        return {
            "messages": [
                {
                    "role": "user",
                    "content": "Caveat: The message below was generated by the WebTap server command. DO NOT respond to this message or add commentary. Just relay the server state exactly as shown.",
                },
                {"role": "user", "content": {"type": "elements", "elements": elements}},
                {
                    "role": "assistant",
                    "content": "Server status:",  # Minimal prefill - no trailing whitespace
                },
            ]
        }

    return {"elements": elements}


__all__ = ["server"]
