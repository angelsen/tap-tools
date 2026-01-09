"""Browser navigation commands.

Commands: navigate, reload, back, forward, page, history
"""

from webtap.app import app
from webtap.commands._builders import info_response, error_response, table_response, rpc_call
from webtap.commands._tips import get_tips


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def navigate(state, url: str, target: str) -> dict:
    """Navigate to URL.

    Args:
        url: URL to navigate to
        target: Target ID (e.g., "9222:abc123")

    Returns:
        Navigation result with frame and loader IDs
    """
    result, error = rpc_call(state, "navigate", url=url, target=target)
    if error:
        return error

    if result.get("error"):
        return error_response(f"Navigation error: {result['error']}")

    return info_response(
        title="Navigation",
        fields={
            "URL": url,
            "Frame ID": result.get("frame_id", ""),
            "Loader ID": result.get("loader_id", ""),
        },
    )


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def reload(state, target: str, ignore_cache: bool = False) -> dict:
    """Reload the current page.

    Args:
        target: Target ID (e.g., "9222:abc123")
        ignore_cache: Force reload ignoring cache
    """
    result, error = rpc_call(state, "reload", target=target, ignore_cache=ignore_cache)
    if error:
        return error

    return info_response(
        title="Page Reload",
        fields={
            "Status": "Page reloaded",
            "Cache": "Ignored" if result.get("ignore_cache") else "Used",
        },
    )


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def back(state, target: str) -> dict:
    """Navigate back in history.

    Args:
        target: Target ID (e.g., "9222:abc123")
    """
    result, error = rpc_call(state, "back", target=target)
    if error:
        return error

    if not result.get("navigated"):
        return info_response(
            title="Navigation Back",
            fields={"Status": result.get("reason", "Cannot go back")},
        )

    return info_response(
        title="Navigation Back",
        fields={
            "Status": "Navigated back",
            "Page": result.get("title", ""),
            "URL": result.get("url", ""),
            "Index": f"{result.get('index', 0) + 1} of {result.get('total', 0)}",
        },
    )


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def forward(state, target: str) -> dict:
    """Navigate forward in history.

    Args:
        target: Target ID (e.g., "9222:abc123")
    """
    result, error = rpc_call(state, "forward", target=target)
    if error:
        return error

    if not result.get("navigated"):
        return info_response(
            title="Navigation Forward",
            fields={"Status": result.get("reason", "Cannot go forward")},
        )

    return info_response(
        title="Navigation Forward",
        fields={
            "Status": "Navigated forward",
            "Page": result.get("title", ""),
            "URL": result.get("url", ""),
            "Index": f"{result.get('index', 0) + 1} of {result.get('total', 0)}",
        },
    )


@app.command(
    display="markdown",
    fastmcp={"enabled": False},
)
def page(state) -> dict:
    """Get current page information."""
    result, error = rpc_call(state, "page")
    if error:
        return error

    tips = get_tips("page")

    return info_response(
        title=result.get("title", "Untitled Page"),
        fields={
            "URL": result.get("url", ""),
            "ID": result.get("id", ""),
            "Type": result.get("type", ""),
        },
        tips=tips,
    )


@app.command(
    display="markdown",
    fastmcp={"type": "resource", "mime_type": "text/markdown"},
)
def history(state) -> dict:
    """Get navigation history."""
    result, error = rpc_call(state, "history")
    if error:
        return error

    entries = result.get("entries", [])

    if not entries:
        return info_response(
            title="Navigation History",
            fields={"Status": "No history entries"},
        )

    # Format rows for table
    rows = []
    for e in entries:
        marker = "→ " if e.get("current") else "  "
        rows.append(
            {
                "": marker,
                "ID": e.get("id", ""),
                "Title": e.get("title", "")[:40],
                "URL": e.get("url", "")[:60],
                "Type": e.get("type", ""),
            }
        )

    return table_response(
        title="Navigation History",
        rows=rows,
        summary=f"{len(entries)} entries",
    )
