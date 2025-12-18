"""Network request monitoring and display commands."""

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import table_response, error_response, format_size
from webtap.commands._tips import get_tips

# Truncation values for REPL mode (compact display)
_REPL_TRUNCATE = {
    "ReqID": {"max": 12, "mode": "end"},
    "URL": {"max": 60, "mode": "middle"},
}

# Truncation values for MCP mode (generous for LLM context)
_MCP_TRUNCATE = {
    "ReqID": {"max": 50, "mode": "end"},
    "URL": {"max": 200, "mode": "middle"},
}


@app.command(
    display="markdown",
    fastmcp=[{"type": "resource", "mime_type": "text/markdown"}, {"type": "tool", "mime_type": "text/markdown"}],
)
def network(
    state,
    status: int = None,  # pyright: ignore[reportArgumentType]
    method: str = None,  # pyright: ignore[reportArgumentType]
    resource_type: str = None,  # pyright: ignore[reportArgumentType]
    url: str = None,  # pyright: ignore[reportArgumentType]
    req_state: str = None,  # pyright: ignore[reportArgumentType]
    show_all: bool = False,
    limit: int = 50,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """List network requests with inline filters.

    Args:
        status: Filter by HTTP status code (e.g., 404, 500)
        method: Filter by HTTP method (e.g., "POST", "GET")
        resource_type: Filter by resource type (e.g., "xhr", "fetch", "websocket")
        url: Filter by URL pattern (supports * wildcard)
        req_state: Filter by state (pending, loading, complete, failed, paused)
        show_all: Bypass noise filter groups
        limit: Max results (default 50)

    Examples:
        network()                    # Default with noise filter
        network(status=404)          # Only 404s
        network(method="POST")       # Only POST requests
        network(resource_type="websocket")  # Only WebSocket
        network(url="*api*")         # URLs containing "api"
        network(req_state="paused")  # Only paused requests
        network(show_all=True)       # Show everything
    """
    # Build params, omitting None values
    params = {"limit": limit, "show_all": show_all}
    if status is not None:
        params["status"] = status
    if method is not None:
        params["method"] = method
    if resource_type is not None:
        params["resource_type"] = resource_type
    if url is not None:
        params["url"] = url
    if req_state is not None:
        params["state"] = req_state

    try:
        result = state.client.call("network", **params)
        requests = result.get("requests", [])
    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    # Mode-specific configuration
    is_repl = _ctx and _ctx.is_repl()

    # Check if any request has pause_stage (to show Pause column)
    has_pause = any(r.get("pause_stage") for r in requests)

    # Build rows with mode-specific formatting
    rows = []
    for r in requests:
        row = {
            "ID": str(r["id"]),
            "ReqID": r["request_id"],
            "Method": r["method"],
            "Status": str(r["status"]) if r["status"] else "-",
            "URL": r["url"],
            "Type": r["type"] or "-",
            # REPL: human-friendly format, MCP: raw bytes for LLM
            "Size": format_size(r["size"]) if is_repl else (r["size"] or 0),
            "State": r.get("state", "-"),
        }
        # Add Pause column if relevant
        if has_pause:
            row["Pause"] = r.get("pause_stage") or "-"
        rows.append(row)

    # Build response with developer guidance
    warnings = []
    if limit and len(requests) == limit:
        warnings.append(f"Showing {limit} most recent (use limit parameter to see more)")

    # Get tips from TIPS.md with context
    combined_tips = []
    if not show_all:
        combined_tips.append("Use show_all=True to bypass filter groups")

    if rows:
        example_id = rows[0]["ID"]
        context_tips = get_tips("network", context={"id": example_id})
        if context_tips:
            combined_tips.extend(context_tips)

    # Use mode-specific truncation
    truncate = _REPL_TRUNCATE if is_repl else _MCP_TRUNCATE

    # Build headers dynamically
    headers = ["ID", "ReqID", "Method", "Status", "URL", "Type", "Size", "State"]
    if has_pause:
        headers.append("Pause")

    return table_response(
        title="Network Requests",
        headers=headers,
        rows=rows,
        summary=f"{len(rows)} requests" if rows else None,
        warnings=warnings,
        tips=combined_tips if combined_tips else None,
        truncate=truncate,
    )
