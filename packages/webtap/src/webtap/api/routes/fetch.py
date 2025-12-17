"""Fetch interception endpoints."""

import asyncio
from typing import Any, Dict

from fastapi import APIRouter

import webtap.api.app as app_module
from webtap.api.models import FailRequest, FetchRequest, FulfillRequest, ResumeRequest
from webtap.api.state import get_full_state

router = APIRouter()


@router.post("/fetch")
async def set_fetch_interception(request: FetchRequest) -> Dict[str, Any]:
    """Enable or disable fetch request interception."""
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    # Wrap blocking CDP calls (Fetch.enable/disable) in thread
    if request.enabled:
        result = await asyncio.to_thread(
            app_module.app_state.service.fetch.enable,
            app_module.app_state.service.cdp,
            response_stage=request.response_stage,
        )
    else:
        result = await asyncio.to_thread(app_module.app_state.service.fetch.disable)

    # Broadcast state change
    app_module.app_state.service._trigger_broadcast()

    # SYNC FIX: Return full state for immediate UI update
    return {**result, "state": get_full_state()}


@router.get("/paused")
async def get_paused_requests() -> Dict[str, Any]:
    """Get list of paused fetch requests.

    Returns:
        Dictionary with paused requests: {requests: [{rowid, request_id, url, method, stage}, ...]}
    """
    if not app_module.app_state:
        return {"requests": [], "error": "WebTap not initialized", "state": get_full_state()}

    paused = app_module.app_state.service.fetch.get_paused_list()
    return {"requests": paused, "state": get_full_state()}


@router.post("/resume")
async def resume_request(request: ResumeRequest) -> Dict[str, Any]:
    """Resume a paused fetch request with optional modifications.

    Args:
        request: Row ID and optional modifications

    Returns:
        Resume result
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    try:
        result = await asyncio.to_thread(
            app_module.app_state.service.fetch.continue_request, request.rowid, request.modifications, request.wait
        )
        return {"resumed": True, "result": result, "state": get_full_state()}
    except Exception as e:
        return {"error": str(e), "state": get_full_state()}


@router.post("/fail")
async def fail_request(request: FailRequest) -> Dict[str, Any]:
    """Fail a paused fetch request.

    Args:
        request: Row ID and failure reason

    Returns:
        Fail result
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    try:
        result = await asyncio.to_thread(app_module.app_state.service.fetch.fail_request, request.rowid, request.reason)
        return {"failed": True, "result": result, "state": get_full_state()}
    except Exception as e:
        return {"error": str(e), "state": get_full_state()}


@router.post("/fulfill")
async def fulfill_request(request: FulfillRequest) -> Dict[str, Any]:
    """Fulfill a paused fetch request with a custom response.

    Args:
        request: Row ID and response details

    Returns:
        Fulfill result
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized", "state": get_full_state()}

    try:
        result = await asyncio.to_thread(
            app_module.app_state.service.fetch.fulfill_request,
            request.rowid,
            request.response_code,
            request.response_headers,
            request.body,
        )
        return {"fulfilled": True, "result": result, "state": get_full_state()}
    except Exception as e:
        return {"error": str(e), "state": get_full_state()}
