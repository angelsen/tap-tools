"""Connection and status endpoints."""

import asyncio
import os
from typing import Any, Dict

from fastapi import APIRouter

import webtap.api.app as app_module
from webtap.api.models import ClearRequest, ConnectRequest
from webtap.api.state import get_full_state

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Quick health check endpoint for extension."""
    return {"status": "ok", "pid": os.getpid()}


@router.get("/info")
async def get_info() -> Dict[str, Any]:
    """Combined endpoint for pages and instance info - reduces round trips."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "pages": [], "pid": os.getpid()}

    # Get pages - wrap blocking HTTP call in thread
    pages_data = await asyncio.to_thread(app_module.app_state.service.list_pages)

    # Get instance info
    connected_to = None
    if app_module.app_state.cdp.is_connected and app_module.app_state.cdp.page_info:
        connected_to = app_module.app_state.cdp.page_info.get("title", "Untitled")

    return {
        "pid": os.getpid(),
        "connected_to": connected_to,
        "events": app_module.app_state.service.event_count,
        "pages": pages_data.get("pages", []),
        "error": pages_data.get("error"),
    }


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Get comprehensive status including connection, events, browser, and fetch details."""
    if not app_module.app_state:
        return {"connected": False, "error": "WebTap not initialized", "events": {"total": 0}}

    return get_full_state()


@router.get("/pages")
async def get_pages() -> Dict[str, Any]:
    """Get available Chrome pages from /json endpoint.

    Returns:
        Dictionary with pages list: {pages: [...]}
    """
    if not app_module.app_state:
        return {"pages": [], "error": "WebTap not initialized"}

    # Wrap blocking HTTP call in thread
    try:
        pages_data = await asyncio.to_thread(app_module.app_state.service.list_pages)
        return pages_data
    except Exception as e:
        return {"pages": [], "error": str(e)}


@router.post("/connect")
async def connect(request: ConnectRequest) -> Dict[str, Any]:
    """Connect to a Chrome page by index or page ID."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    # Validate: must have exactly one of page or page_id
    if request.page is not None and request.page_id is not None:
        return {"error": "Cannot specify both 'page' and 'page_id'", "state": get_full_state()}
    if request.page is None and request.page_id is None:
        return {"error": "Must specify 'page' or 'page_id'", "state": get_full_state()}

    # Wrap blocking CDP calls (connect + enable domains) in thread
    result = await asyncio.to_thread(
        app_module.app_state.service.connect_to_page, page_index=request.page, page_id=request.page_id
    )

    # SYNC FIX: Return full state for immediate UI update
    return {**result, "state": get_full_state()}


@router.post("/disconnect")
async def disconnect() -> Dict[str, Any]:
    """Disconnect from currently connected page."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    # Wrap blocking CDP calls (fetch.disable + disconnect) in thread
    result = await asyncio.to_thread(app_module.app_state.service.disconnect)

    # SYNC FIX: Return full state for immediate UI update
    return {**result, "state": get_full_state()}


@router.post("/clear")
async def clear_data(request: ClearRequest) -> Dict[str, Any]:
    """Clear various data stores.

    Args:
        request: Flags for what to clear

    Returns:
        Dictionary with cleared list: {cleared: [...]}
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    cleared = []

    # Clear CDP events
    if request.events:
        await asyncio.to_thread(app_module.app_state.service.clear_events)
        cleared.append("events")

    # Clear browser console
    if request.console:
        if app_module.app_state.cdp and app_module.app_state.cdp.is_connected:
            success = await asyncio.to_thread(app_module.app_state.service.console.clear_browser_console)
            if success:
                cleared.append("console")
        else:
            cleared.append("console (not connected)")

    # SYNC FIX: Return full state for immediate UI update
    return {"cleared": cleared, "state": get_full_state()}
