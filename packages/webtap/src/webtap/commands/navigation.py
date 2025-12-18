"""Browser navigation commands."""

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import info_response, error_response, table_response
from webtap.commands._tips import get_tips


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def navigate(state, url: str) -> dict:
    """Navigate to URL.

    Args:
        url: URL to navigate to

    Returns:
        Navigation result with frame and loader IDs
    """
    try:
        result = state.client.call("navigate", url=url)

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

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(f"Navigation failed: {e}")


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def reload(state, ignore_cache: bool = False) -> dict:
    """Reload the current page.

    Args:
        ignore_cache: Force reload ignoring cache
    """
    try:
        result = state.client.call("reload", ignore_cache=ignore_cache)

        return info_response(
            title="Page Reload",
            fields={
                "Status": "Page reloaded",
                "Cache": "Ignored" if result.get("ignore_cache") else "Used",
            },
        )

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(f"Reload failed: {e}")


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def back(state) -> dict:
    """Navigate back in history."""
    try:
        result = state.client.call("back")

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

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(f"Back navigation failed: {e}")


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def forward(state) -> dict:
    """Navigate forward in history."""
    try:
        result = state.client.call("forward")

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

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(f"Forward navigation failed: {e}")


@app.command(
    display="markdown",
    fastmcp={"type": "resource", "mime_type": "text/markdown"},
)
def page(state) -> dict:
    """Get current page information."""
    try:
        result = state.client.call("page")
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

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(f"Page info failed: {e}")


@app.command(
    display="markdown",
    fastmcp={"type": "resource", "mime_type": "text/markdown"},
)
def history(state) -> dict:
    """Get navigation history."""
    try:
        result = state.client.call("history")
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

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(f"History failed: {e}")
