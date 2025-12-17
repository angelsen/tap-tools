"""Filter group management endpoints."""

import asyncio
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

import webtap.api.app as app_module
from webtap.api.state import get_full_state

router = APIRouter()


class FilterGroupCreate(BaseModel):
    """Request body for creating a filter group."""

    hide: dict  # {"types": [...], "urls": [...]}


@router.get("/filters/status")
async def get_filter_status() -> dict[str, Any]:
    """Get all filter groups with enabled status."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "groups": {}}

    fm = app_module.app_state.service.filters
    return fm.get_status()


@router.post("/filters/add/{name}")
async def add_filter_group(name: str, body: FilterGroupCreate) -> dict[str, Any]:
    """Add a new filter group.

    Args:
        name: Group name
        body: Hide configuration {"hide": {"types": [...], "urls": [...]}}

    Returns:
        Success status
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    fm = app_module.app_state.service.filters

    def add():
        fm.add(name, body.hide)
        return True

    await asyncio.to_thread(add)
    app_module.app_state.service._trigger_broadcast()

    return {"added": True, "name": name, "state": get_full_state()}


@router.post("/filters/remove/{name}")
async def remove_filter_group(name: str) -> dict[str, Any]:
    """Remove a filter group.

    Args:
        name: Group name to remove

    Returns:
        Success status
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    fm = app_module.app_state.service.filters

    def remove():
        return fm.remove(name)

    result = await asyncio.to_thread(remove)
    if result:
        app_module.app_state.service._trigger_broadcast()
        return {"removed": True, "name": name, "state": get_full_state()}
    return {"removed": False, "error": f"Group '{name}' not found", "state": get_full_state()}


@router.post("/filters/enable/{name}")
async def enable_filter_group(name: str) -> dict[str, Any]:
    """Enable a filter group (in-memory).

    Args:
        name: Group name to enable

    Returns:
        Success status
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    fm = app_module.app_state.service.filters
    result = fm.enable(name)

    if result:
        app_module.app_state.service._trigger_broadcast()
        return {"enabled": True, "name": name, "state": get_full_state()}
    return {"enabled": False, "error": f"Group '{name}' not found", "state": get_full_state()}


@router.post("/filters/disable/{name}")
async def disable_filter_group(name: str) -> dict[str, Any]:
    """Disable a filter group (in-memory).

    Args:
        name: Group name to disable

    Returns:
        Success status
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    fm = app_module.app_state.service.filters
    result = fm.disable(name)

    if result:
        app_module.app_state.service._trigger_broadcast()
        return {"disabled": True, "name": name, "state": get_full_state()}
    return {"disabled": False, "error": f"Group '{name}' not found", "state": get_full_state()}


@router.post("/filters/enable-all")
async def enable_all_filters() -> dict[str, Any]:
    """Enable all filter groups."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    fm = app_module.app_state.service.filters
    for name in fm.groups:
        fm.enable(name)
    app_module.app_state.service._trigger_broadcast()
    return {"enabled": list(fm.enabled), "state": get_full_state()}


@router.post("/filters/disable-all")
async def disable_all_filters() -> dict[str, Any]:
    """Disable all filter groups."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    fm = app_module.app_state.service.filters
    fm.enabled.clear()
    app_module.app_state.service._trigger_broadcast()
    return {"enabled": [], "state": get_full_state()}


@router.post("/filters/reload")
async def reload_filters() -> dict[str, Any]:
    """Reload filter groups from disk.

    Returns:
        Dictionary with reload status
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized"}

    fm = app_module.app_state.service.filters
    loaded = await asyncio.to_thread(fm.load)

    if loaded:
        app_module.app_state.service._trigger_broadcast()
        return {"loaded": True, "groups": len(fm.groups), "path": str(fm.filter_path)}
    return {"loaded": False, "error": f"Failed to load from {fm.filter_path}"}
