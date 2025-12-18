"""Chrome browser connection management commands."""

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import info_response, table_response, error_response
from webtap.commands._tips import get_mcp_description, get_tips

_connect_desc = get_mcp_description("connect")
_disconnect_desc = get_mcp_description("disconnect")
_clear_desc = get_mcp_description("clear")

# Truncation values for pages() REPL mode (compact display)
_PAGES_REPL_TRUNCATE = {
    "Title": {"max": 20, "mode": "end"},
    "URL": {"max": 30, "mode": "middle"},
    "ID": {"max": 6, "mode": "end"},
}

# Truncation values for pages() MCP mode (generous for LLM context)
_PAGES_MCP_TRUNCATE = {
    "Title": {"max": 100, "mode": "end"},
    "URL": {"max": 200, "mode": "middle"},
    "ID": {"max": 50, "mode": "end"},
}


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _connect_desc or ""}
)
def connect(state, page: int = None, page_id: str = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Connect to Chrome page and enable all required domains.

    Args:
        page: Connect by page index (0-based)
        page_id: Connect by page ID

    Note: If neither is specified, connects to first available page.
          Cannot specify both page and page_id.

    Examples:
        connect()                    # First page
        connect(page=2)             # Third page (0-indexed)
        connect(page_id="xyz")      # Specific page ID

    Returns:
        Connection status in markdown
    """
    try:
        # Build params - default to page=0 when no params given
        params = {}
        if page is not None:
            params["page"] = page
        if page_id is not None:
            params["page_id"] = page_id
        if not params:
            params["page"] = 0  # Connect to first page by default

        result = state.client.call("connect", **params)
    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    # Success - return formatted info with full URL
    return info_response(
        title="Connection Established",
        fields={"Page": result.get("title", "Unknown"), "URL": result.get("url", "")},
    )


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _disconnect_desc or ""}
)
def disconnect(state) -> dict:
    """Disconnect from Chrome."""
    try:
        state.client.call("disconnect")
    except RPCError as e:
        # INVALID_STATE means not connected
        if e.code == "INVALID_STATE":
            return info_response(title="Disconnect Status", fields={"Status": "Not connected"})
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    return info_response(title="Disconnect Status", fields={"Status": "Disconnected"})


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _clear_desc or ""}
)
def clear(state, events: bool = True, console: bool = False) -> dict:
    """Clear various data stores.

    Args:
        events: Clear CDP events (default: True)
        console: Clear console messages (default: False)

    Examples:
        clear()                                    # Clear events only
        clear(events=True, console=True)          # Clear events and console
        clear(events=False, console=True)         # Console only

    Returns:
        Summary of what was cleared
    """
    try:
        result = state.client.call("clear", events=events, console=console)
    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    # Build cleared list from result
    cleared = result.get("cleared", [])

    if not cleared:
        return info_response(
            title="Clear Status",
            fields={"Result": "Nothing to clear (specify events=True or console=True)"},
        )

    return info_response(title="Clear Status", fields={"Cleared": ", ".join(cleared)})


@app.command(
    display="markdown",
    fastmcp={"type": "resource", "mime_type": "text/markdown"},
)
def pages(state, _ctx: ExecutionContext = None) -> dict:  # pyright: ignore[reportArgumentType]
    """List available Chrome pages.

    Returns:
        Table of available pages in markdown
    """
    try:
        result = state.client.call("pages")
        pages_list = result.get("pages", [])
    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    # Format rows for table with FULL data
    rows = [
        {
            "Index": str(i),
            "Title": p.get("title", "Untitled"),  # Full title
            "URL": p.get("url", ""),  # Full URL
            "ID": p.get("id", ""),  # Full ID
            "Connected": "Yes" if p.get("is_connected") else "No",
        }
        for i, p in enumerate(pages_list)
    ]

    # Get contextual tips
    tips = None
    if rows:
        # Find connected page or first page
        connected_row = next((r for r in rows if r["Connected"] == "Yes"), rows[0])
        page_index = connected_row["Index"]

        # Get page_id for the example page
        connected_page = next((p for p in pages_list if str(pages_list.index(p)) == page_index), None)
        page_id = connected_page.get("id", "")[:6] if connected_page else ""

        tips = get_tips("pages", context={"index": page_index, "page_id": page_id})

    # Build contextual warnings
    warnings = []
    if any(r["Connected"] == "Yes" for r in rows):
        warnings.append("Already connected - call connect(page=N) to switch pages")

    # Use mode-specific truncation
    is_repl = _ctx and _ctx.is_repl()
    truncate = _PAGES_REPL_TRUNCATE if is_repl else _PAGES_MCP_TRUNCATE

    # Build markdown response
    return table_response(
        title="Chrome Pages",
        headers=["Index", "Title", "URL", "ID", "Connected"],
        rows=rows,
        summary=f"{len(pages_list)} page{'s' if len(pages_list) != 1 else ''} available",
        warnings=warnings if warnings else None,
        tips=tips,
        truncate=truncate,
    )


@app.command(display="markdown", fastmcp={"type": "resource", "mime_type": "text/markdown"})
def status(state) -> dict:
    """Get connection status.

    Returns:
        Status information in markdown
    """
    try:
        status_data = state.client.call("status")
    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    # Check if connected
    if not status_data.get("connected"):
        return error_response("Not connected to any page. Use connect() first.")

    # Build formatted response with full URL
    page = status_data.get("page", {})
    return info_response(
        title="Connection Status",
        fields={
            "Page": page.get("title", "Unknown"),
            "URL": page.get("url", ""),
            "Events": f"{status_data.get('events', {}).get('total', 0)} stored",
            "Fetch": "Enabled" if status_data.get("fetch", {}).get("enabled") else "Disabled",
        },
    )
