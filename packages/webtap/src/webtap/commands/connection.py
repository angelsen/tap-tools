"""Chrome browser connection management commands."""

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.commands._builders import info_response, table_response, error_response, rpc_call
from webtap.commands._tips import get_mcp_description, get_tips

_clear_desc = get_mcp_description("clear")

# Truncation values for targets() REPL mode (compact display)
_TARGETS_REPL_TRUNCATE = {
    "Title": {"max": 25, "mode": "end"},
    "URL": {"max": 35, "mode": "middle"},
}

# Truncation values for targets() MCP mode (generous for LLM context)
_TARGETS_MCP_TRUNCATE = {
    "Title": {"max": 100, "mode": "end"},
    "URL": {"max": 200, "mode": "middle"},
}

# Shared label mappings for target type and state display
_TYPE_LABELS = {
    "page": "page",
    "service_worker": "sw",
    "background_page": "bg",
    "worker": "worker",
}

_STATE_LABELS = {
    "attached": "attached",
    "connecting": "connecting",
    "suspended": "suspended",
}


@app.command(
    display="markdown",
    fastmcp={"enabled": False},
)
def watch(
    state,
    targets: list = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Watch one or more Chrome targets.

    Args:
        targets: List of target IDs (e.g., ["9222:f8134d"])

    Examples:
        watch(["9222:f8"])              # Watch single target
        watch(["9222:f8", "9222:ab"])   # Watch multiple targets

    Returns:
        Watch results in markdown
    """
    if not targets:
        return error_response(
            "No targets specified",
            suggestions=[
                "targets()                    # List available targets",
                "watch(['9222:f8'])           # Watch by target ID",
            ],
        )

    result, error = rpc_call(state, "watch", targets=targets)
    if error:
        return error

    watched = result.get("watched", [])
    summary_parts = []
    for w in watched:
        target_id = w.get("target", "")
        if w.get("error"):
            summary_parts.append(f"{target_id}: {w['error']}")
        elif w.get("already_attached"):
            summary_parts.append(f"{target_id}: already attached")
        elif w.get("state") == "connecting":
            summary_parts.append(f"{target_id}: connecting")
        elif w.get("state") == "attached" or w.get("attached"):
            summary_parts.append(f"{target_id}: attached")
        else:
            summary_parts.append(f"{target_id}: watched (not yet attached)")

    return info_response(
        title="Watch",
        fields={"Targets": "\n".join(summary_parts) if summary_parts else "None"},
    )


@app.command(
    display="markdown",
    fastmcp={"enabled": False},
)
def unwatch(state, targets: list = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Stop watching targets.

    Args:
        targets: List of target IDs. None = unwatch all.

    Examples:
        unwatch()                       # Unwatch all
        unwatch(["9222:f8"])            # Unwatch specific target
    """
    if targets:
        result_data, error = rpc_call(state, "unwatch", targets=targets)
    else:
        result_data, error = rpc_call(state, "unwatch")
    if error:
        return error

    unwatched = result_data.get("unwatched", [])
    count = len(unwatched)
    return info_response(
        title="Unwatch",
        fields={"Status": f"Unwatched {count} target{'s' if count != 1 else ''}"},
    )


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
        return error_response("Not connected to any page. Use watch() first.")

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
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def targets(
    state,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """List all discoverable Chrome targets with watch/attach state.

    Returns:
        Table of all targets with Type, Title, URL, Watched, State
    """
    result, error = rpc_call(state, "targets")
    if error:
        return error
    targets_list = result.get("targets", [])

    has_parents = any(t.get("parent") for t in targets_list)

    rows = [
        {
            "Target": t.get("target", ""),
            "Type": _TYPE_LABELS.get(t.get("type", "page"), t.get("type", "page")),
            "Title": t.get("title", "Untitled"),
            "URL": t.get("url", ""),
            "Watched": "yes" if t.get("watched") else "",
            "State": _STATE_LABELS.get(t.get("state", ""), "") if t.get("watched") else "",
            **({"Parent": t.get("parent", "")} if has_parents else {}),
        }
        for t in targets_list
    ]

    tips = None
    if rows:
        example_target = rows[0]["Target"]
        tips = get_tips("targets", context={"target": example_target})

    is_repl = _ctx and _ctx.is_repl()
    truncate = _TARGETS_REPL_TRUNCATE if is_repl else _TARGETS_MCP_TRUNCATE

    headers = ["Target", "Type", "Title", "URL", "Watched", "State"]
    if has_parents:
        headers.append("Parent")

    return table_response(
        title="Chrome Targets",
        headers=headers,
        rows=rows,
        summary=f"{len(targets_list)} target{'s' if len(targets_list) != 1 else ''} available",
        tips=tips,
        truncate=truncate,
    )


@app.command(
    display="markdown",
    fastmcp=[
        {"type": "resource", "mime_type": "text/markdown"},
        {"type": "tool", "mime_type": "text/markdown"},
    ],
)
def watching(
    state,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Show watched targets with state and event count.

    Returns:
        Table of watched targets with state indicators
    """
    result, error = rpc_call(state, "targets")
    if error:
        return error
    targets_list = result.get("targets", [])

    # Filter to watched + auto-attached (opener-matched popups)
    watched = [t for t in targets_list if t.get("watched") or t.get("auto_attached")]

    if not watched:
        return info_response(title="Not Watching", fields={"Status": "No watched targets"})

    has_parents = any(t.get("parent") for t in watched)

    rows = [
        {
            "Target": t.get("target", ""),
            "Type": _TYPE_LABELS.get(t.get("type", "page"), t.get("type", "page")),
            "Title": t.get("title", "Untitled"),
            "URL": t.get("url", ""),
            "State": _STATE_LABELS.get(t.get("state", ""), t.get("state", "")),
            **({"Parent": t.get("parent", "")} if has_parents else {}),
        }
        for t in watched
    ]

    is_repl = _ctx and _ctx.is_repl()
    truncate = _TARGETS_REPL_TRUNCATE if is_repl else _TARGETS_MCP_TRUNCATE

    headers = ["Target", "Type", "Title", "URL", "State"]
    if has_parents:
        headers.append("Parent")

    return table_response(
        title="Watching",
        headers=headers,
        rows=rows,
        summary=f"{len(watched)} target{'s' if len(watched) != 1 else ''} watched",
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
                "Targets": str(p.get("target_count", 0)),
                "Watched": str(p.get("watched_count", 0)),
                "Status": p.get("status", "unknown"),
            }
        )

    return table_response(
        title="Registered Ports",
        headers=["Port", "Targets", "Watched", "Status"],
        rows=rows,
        summary=f"{len(ports_list)} port{'s' if len(ports_list) != 1 else ''} registered",
    )
