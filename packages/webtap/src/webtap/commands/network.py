"""Network request monitoring and display commands."""

from replkit2.types import ExecutionContext

from webtap.app import app
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
    status: int = None,  # type: ignore[reportArgumentType]
    method: str = None,  # type: ignore[reportArgumentType]
    type: str = None,  # type: ignore[reportArgumentType]
    url: str = None,  # type: ignore[reportArgumentType]
    all: bool = False,
    limit: int = 20,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """List network requests with inline filters.

    Args:
        status: Filter by HTTP status code (e.g., 404, 500)
        method: Filter by HTTP method (e.g., "POST", "GET")
        type: Filter by resource type (e.g., "xhr", "fetch", "websocket")
        url: Filter by URL pattern (supports * wildcard)
        all: Bypass noise filter groups
        limit: Max results (default 20)

    Examples:
        network()                    # Default with noise filter
        network(status=404)          # Only 404s
        network(method="POST")       # Only POST requests
        network(type="websocket")    # Only WebSocket
        network(url="*api*")         # URLs containing "api"
        network(all=True)            # Show everything
    """
    # Check connection via daemon status
    try:
        daemon_status = state.client.status()
        if not daemon_status.get("connected"):
            return error_response("Not connected to any page. Use connect() first.")
    except Exception as e:
        return error_response(str(e))

    # Get network requests from daemon with inline filters
    try:
        requests = state.client.network(
            status=status,
            method=method,
            type_filter=type,
            url=url,
            apply_groups=not all,
            limit=limit,
        )
    except Exception as e:
        return error_response(str(e))

    # Mode-specific configuration
    is_repl = _ctx and _ctx.is_repl()

    # Build rows with mode-specific formatting
    rows = [
        {
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
        for r in requests
    ]

    # Build response with developer guidance
    warnings = []
    if limit and len(requests) == limit:
        warnings.append(f"Showing first {limit} results (use limit parameter to see more)")

    # Get tips from TIPS.md with context
    combined_tips = []
    if not all:
        combined_tips.append("Use all=True to bypass filter groups")

    if rows:
        example_id = rows[0]["ID"]
        context_tips = get_tips("network", context={"id": example_id})
        if context_tips:
            combined_tips.extend(context_tips)

    # Use mode-specific truncation
    truncate = _REPL_TRUNCATE if is_repl else _MCP_TRUNCATE

    return table_response(
        title="Network Requests",
        headers=["ID", "ReqID", "Method", "Status", "URL", "Type", "Size", "State"],
        rows=rows,
        summary=f"{len(rows)} requests" if rows else None,
        warnings=warnings,
        tips=combined_tips if combined_tips else None,
        truncate=truncate,
    )
