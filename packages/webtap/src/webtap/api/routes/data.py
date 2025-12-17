"""Network and console data endpoints."""

import asyncio
from typing import Any

from fastapi import APIRouter

import webtap.api.app as app_module

router = APIRouter()


@router.get("/network")
async def get_network_requests(
    limit: int = 20,
    status: int | None = None,
    method: str | None = None,
    type_filter: str | None = None,
    url: str | None = None,
    apply_groups: bool = True,
    order: str = "desc",
) -> dict[str, Any]:
    """Get network requests from HAR summary view.

    Args:
        limit: Maximum results to return
        status: Filter by HTTP status code
        method: Filter by HTTP method
        type_filter: Filter by resource type
        url: Filter by URL pattern (supports * wildcard)
        apply_groups: Apply enabled filter groups (default True)
        order: Sort order - "desc" (newest first) or "asc" (oldest first)

    Returns:
        Dictionary with processed requests: {requests: [...]}
    """
    if not app_module.app_state:
        return {"requests": [], "error": "WebTap not initialized"}

    def query_network():
        assert app_module.app_state is not None
        return app_module.app_state.service.network.get_requests(
            limit=limit,
            status=status,
            method=method,
            type_filter=type_filter,
            url=url,
            apply_groups=apply_groups,
            order=order,
        )

    requests = await asyncio.to_thread(query_network)
    return {"requests": requests}


@router.get("/request/{row_id}")
async def get_request_details(row_id: int) -> dict[str, Any]:
    """Get HAR entry with nested structure.

    Args:
        row_id: Row ID from network() output

    Returns:
        HAR-structured entry or error
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized"}

    def fetch_details():
        assert app_module.app_state is not None
        return app_module.app_state.service.network.get_request_details(row_id)

    entry = await asyncio.to_thread(fetch_details)
    if entry:
        return {"entry": entry}
    return {"error": f"Request {row_id} not found"}


@router.get("/body/by-request-id/{request_id}")
async def get_body_by_request_id(request_id: str) -> dict[str, Any]:
    """Fetch response body by CDP request ID.

    Args:
        request_id: CDP request ID

    Returns:
        Dictionary with body data: {body, base64Encoded}
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized"}

    def fetch():
        assert app_module.app_state is not None
        return app_module.app_state.service.network.fetch_body(request_id)

    result = await asyncio.to_thread(fetch)
    if result:
        return result
    return {"error": f"Could not fetch body for {request_id}"}


@router.get("/console")
async def get_console_messages(limit: int = 50, level: str | None = None) -> dict[str, Any]:
    """Get console messages with extracted fields.

    Args:
        limit: Maximum results to return
        level: Optional filter by level (error, warning, log, info)

    Returns:
        Dictionary with processed messages: {messages: [...]}
    """
    if not app_module.app_state:
        return {"messages": [], "error": "WebTap not initialized"}

    def query_console():
        assert app_module.app_state is not None
        rows = app_module.app_state.service.console.get_recent_messages(limit, level)
        return [
            {
                "id": r[0],
                "level": (r[1] or "log").upper(),
                "source": r[2] or "console",
                "message": r[3] or "",
                "timestamp": float(r[4]) if r[4] else 0,
            }
            for r in rows
        ]

    messages = await asyncio.to_thread(query_console)
    return {"messages": messages}
