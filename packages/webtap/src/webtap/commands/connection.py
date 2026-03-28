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
    typer={"enabled": False},
)
def watch(
    state,
    targets: list = None,  # pyright: ignore[reportArgumentType]
    urls: list = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Watch Chrome targets by ID and/or URL pattern.

    Args:
        targets: List of target IDs (e.g., ["9222:f8134d"])
        urls: List of URL substring patterns (e.g., ["nnebkiakalpfhlpcpekfpmodhkcinbhe"])

    Examples:
        watch(["9222:f8"])                            # Watch single target
        watch(urls=["nnebkiakalpfhlpcpekfpmodhkcinbhe"])  # Watch by extension ID
        watch(["9222:f8"], urls=["example.com"])      # Both

    Returns:
        Watch results in markdown
    """
    if not targets and not urls:
        return error_response(
            "No targets or URL patterns specified",
            suggestions=[
                "targets()                                    # List available targets",
                "watch(['9222:f8'])                           # Watch by target ID",
                "watch(urls=['nnebkiak...'])                  # Watch by URL pattern",
            ],
        )

    kwargs: dict = {}
    if targets:
        kwargs["targets"] = targets
    if urls:
        kwargs["urls"] = urls

    result, error = rpc_call(state, "watch", **kwargs)
    if error:
        return error

    summary_parts = []

    # Target watch results
    watched = result.get("watched", [])
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

    # Pattern watch results
    watched_patterns = result.get("watched_patterns", [])
    for w in watched_patterns:
        if w.get("target"):
            summary_parts.append(f"{w['target']}: attached (pattern: {w.get('pattern', '')})")
        elif w.get("pattern") and w.get("watched"):
            summary_parts.append(f"Pattern '{w['pattern']}': watching")

    return info_response(
        title="Watch",
        fields={"Targets": "\n".join(summary_parts) if summary_parts else "None"},
    )


@app.command(
    display="markdown",
    fastmcp={"enabled": False},
    typer={"enabled": False},
)
def unwatch(state, targets: list = None, urls: list = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Stop watching targets and/or URL patterns.

    Args:
        targets: List of target IDs. None = unwatch all.
        urls: List of URL patterns to unwatch.

    Examples:
        unwatch()                       # Unwatch all
        unwatch(["9222:f8"])            # Unwatch specific target
        unwatch(urls=["nnebkiak..."])   # Unwatch URL pattern
    """
    kwargs: dict = {}
    if targets:
        kwargs["targets"] = targets
    if urls:
        kwargs["urls"] = urls

    if kwargs:
        result_data, error = rpc_call(state, "unwatch", **kwargs)
    else:
        result_data, error = rpc_call(state, "unwatch")
    if error:
        return error

    unwatched = result_data.get("unwatched", [])
    unwatched_patterns = result_data.get("unwatched_patterns", [])
    count = len(unwatched) + len(unwatched_patterns)
    return info_response(
        title="Unwatch",
        fields={"Status": f"Unwatched {count} item{'s' if count != 1 else ''}"},
    )


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _clear_desc or ""}
)
def clear(state) -> dict:
    """Clear CDP events from all connected targets.

    Clears stored network requests, console messages, and other CDP events.

    Examples:
        clear()

    Returns:
        Summary of what was cleared
    """
    result, error = rpc_call(state, "clear")
    if error:
        return error

    cleared = result.get("cleared", [])
    return info_response(title="Clear Status", fields={"Cleared": ", ".join(cleared) or "nothing"})


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
