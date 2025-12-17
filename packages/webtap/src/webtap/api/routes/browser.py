"""Browser inspection and error management endpoints."""

import asyncio
from typing import Any, Dict

from fastapi import APIRouter

import webtap.api.app as app_module
from webtap.api.state import get_full_state

router = APIRouter()


@router.post("/browser/start-inspect")
async def start_inspect() -> Dict[str, Any]:
    """Enable CDP element inspection mode."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    if not app_module.app_state.cdp.is_connected:
        return {"error": "Not connected to a page", "state": get_full_state()}

    # Wrap blocking CDP calls (DOM.enable, CSS.enable, Overlay.enable, setInspectMode) in thread
    result = await asyncio.to_thread(app_module.app_state.service.dom.start_inspect)

    return {**result, "state": get_full_state()}


@router.post("/browser/stop-inspect")
async def stop_inspect() -> Dict[str, Any]:
    """Disable CDP element inspection mode."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    # Wrap blocking CDP call (Overlay.setInspectMode) in thread
    result = await asyncio.to_thread(app_module.app_state.service.dom.stop_inspect)

    return {**result, "state": get_full_state()}


@router.post("/browser/clear")
async def clear_selections() -> Dict[str, Any]:
    """Clear all element selections."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    app_module.app_state.service.dom.clear_selections()

    return {"success": True, "selections": {}, "state": get_full_state()}


@router.post("/errors/dismiss")
async def dismiss_error() -> Dict[str, Any]:
    """Dismiss the current error."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    app_module.app_state.error_state = None

    # Broadcast state change
    app_module.app_state.service._trigger_broadcast()

    return {"success": True, "state": get_full_state()}
