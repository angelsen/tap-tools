"""Chrome browser connection management commands."""

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import info_response, table_response, error_response, rpc_call
from webtap.commands._tips import get_mcp_description, get_tips

_clear_desc = get_mcp_description("clear")

# Truncation values for pages() REPL mode (compact display)
_PAGES_REPL_TRUNCATE = {
    "Title": {"max": 25, "mode": "end"},
    "URL": {"max": 35, "mode": "middle"},
    # Target is already short (e.g., "9222:f8134d")
}

# Truncation values for pages() MCP mode (generous for LLM context)
_PAGES_MCP_TRUNCATE = {
    "Title": {"max": 100, "mode": "end"},
    "URL": {"max": 200, "mode": "middle"},
}

# Truncation values for targets() - same pattern
_TARGETS_REPL_TRUNCATE = {
    "Title": {"max": 25, "mode": "end"},
    "URL": {"max": 35, "mode": "middle"},
}
_TARGETS_MCP_TRUNCATE = {
    "Title": {"max": 100, "mode": "end"},
    "URL": {"max": 200, "mode": "middle"},
}


@app.command(
    display="markdown",
    fastmcp={"enabled": False},
)
def connect(
    state,
    target: str = "",
) -> dict:
    """Connect to Chrome page by target ID.

    Args:
        target: Target ID in format "port:short_id" (e.g., "9222:f8134d", "9224:24")

    Examples:
        connect("9222:f8")     # Connect by target (prefix match)
        connect("9224:24")     # Connect to Android Chrome

    Returns:
        Connection status in markdown
    """
    if not target:
        return error_response(
            "No target specified",
            suggestions=[
                "pages()             # List available targets",
                "connect('9222:f8')  # Connect by target ID",
            ],
        )

    result, error = rpc_call(state, "connect", target=target)
    if error:
        return error

    # Success - return formatted info with full URL
    return info_response(
        title="Connection Established",
        fields={"Page": result.get("title", "Unknown"), "URL": result.get("url", "")},
    )


@app.command(
    display="markdown",
    fastmcp={"enabled": False},
)
def disconnect(state, target: str = "") -> dict:
    """Disconnect from Chrome.

    Args:
        target: Target ID to disconnect. If empty, disconnects all targets.

    Examples:
        disconnect()           # Disconnect all targets
        disconnect("9222:f8")  # Disconnect specific target
    """
    try:
        if target:
            state.client.call("disconnect", target=target)
        else:
            state.client.call("disconnect")
    except RPCError as e:
        # INVALID_STATE means not connected
        if e.code == "INVALID_STATE":
            return info_response(title="Disconnect Status", fields={"Status": "Not connected"})
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    status = f"Disconnected from {target}" if target else "Disconnected from all targets"
    return info_response(title="Disconnect Status", fields={"Status": status})


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
    result, error = rpc_call(state, "clear", events=events, console=console)
    if error:
        return error

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
    fastmcp={"enabled": False},
)
def pages(
    state,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """List available Chrome pages from all registered ports.

    Returns:
        Table of available pages with target IDs
    """
    result, error = rpc_call(state, "pages")
    if error:
        return error
    pages_list = result.get("pages", [])

    # Format rows with Target first
    rows = [
        {
            "Target": p.get("target", ""),
            "Title": p.get("title", "Untitled"),
            "URL": p.get("url", ""),
            "Connected": "Yes" if p.get("connected") else "No",
        }
        for p in pages_list
    ]

    # Get contextual tips with target example
    tips = None
    if rows:
        connected_row = next((r for r in rows if r["Connected"] == "Yes"), rows[0])
        example_target = connected_row["Target"]
        tips = get_tips("pages", context={"target": example_target})

    # Build contextual warnings
    warnings = []
    if any(r["Connected"] == "Yes" for r in rows):
        warnings.append("Already connected - call connect('...') to switch")

    # Use mode-specific truncation
    is_repl = _ctx and _ctx.is_repl()
    truncate = _PAGES_REPL_TRUNCATE if is_repl else _PAGES_MCP_TRUNCATE

    # Build markdown response
    return table_response(
        title="Chrome Pages",
        headers=["Target", "Title", "URL", "Connected"],
        rows=rows,
        summary=f"{len(pages_list)} page{'s' if len(pages_list) != 1 else ''} available",
        warnings=warnings if warnings else None,
        tips=tips,
        truncate=truncate,
    )


@app.command(
    display="markdown",
    fastmcp={"enabled": False},
)
def status(state) -> dict:
    """Get connection status.

    Returns:
        Status information in markdown
    """
    status_data, error = rpc_call(state, "status")
    if error:
        return error

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


@app.command(
    display="markdown",
    fastmcp={"type": "resource", "mime_type": "text/markdown"},
)
def targets(
    state,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Show connected targets and their tracking status.

    Returns:
        Table of connected targets with "Tracked" column
    """
    result, error = rpc_call(state, "status")
    if error:
        return error

    connections = result.get("connections", [])
    tracked = set(result.get("active_targets") or [])

    if not connections:
        return info_response(title="No Targets", fields={"Status": "No active connections"})

    # Build rows with full data (truncation handled by element config)
    rows = []
    for conn in connections:
        target_id = conn.get("target", "")
        rows.append(
            {
                "Target": target_id,
                "Title": conn.get("title") or "",
                "URL": conn.get("url") or "",
                "Tracked": "Yes" if not tracked or target_id in tracked else "No",
            }
        )

    # Get contextual tips with target example
    tips = None
    if rows:
        example_target = rows[0]["Target"]
        tips = get_tips("targets", context={"target": example_target})

    # Use mode-specific truncation
    is_repl = _ctx and _ctx.is_repl()
    truncate = _TARGETS_REPL_TRUNCATE if is_repl else _TARGETS_MCP_TRUNCATE

    return table_response(
        title="Connected Targets",
        headers=["Target", "Title", "URL", "Tracked"],
        rows=rows,
        summary=f"{len(connections)} target{'s' if len(connections) != 1 else ''} connected",
        tips=tips,
        truncate=truncate,
    )


@app.command(
    display="markdown",
    fastmcp={"enabled": False},
    typer={"enabled": False},
)
def ports(state) -> dict:
    """Show registered debug ports.

    Returns:
        Table of ports with page and connection counts
    """
    result, error = rpc_call(state, "ports.list")
    if error:
        return error

    ports_list = result.get("ports", [])

    if not ports_list:
        return info_response(title="No Ports", fields={"Status": "No ports registered"})

    rows = []
    for p in ports_list:
        rows.append(
            {
                "Port": str(p.get("port")),
                "Pages": str(p.get("page_count", 0)),
                "Connected": str(p.get("connection_count", 0)),
                "Status": p.get("status", "unknown"),
            }
        )

    return table_response(
        title="Registered Ports",
        headers=["Port", "Pages", "Connected", "Status"],
        rows=rows,
        summary=f"{len(ports_list)} port{'s' if len(ports_list) != 1 else ''} registered",
    )
