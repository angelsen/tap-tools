"""Browser page navigation and history commands."""

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.commands._builders import check_connection, info_response, table_response, error_response
from webtap.commands._tips import get_mcp_description, get_tips

_navigate_desc = get_mcp_description("navigate")
_reload_desc = get_mcp_description("reload")
_back_desc = get_mcp_description("back")
_forward_desc = get_mcp_description("forward")

# Truncation values for history() REPL mode (compact display)
_HISTORY_REPL_TRUNCATE = {
    "Title": {"max": 40, "mode": "end"},
    "URL": {"max": 50, "mode": "middle"},
}

# Truncation values for history() MCP mode (generous for LLM context)
_HISTORY_MCP_TRUNCATE = {
    "Title": {"max": 100, "mode": "end"},
    "URL": {"max": 200, "mode": "middle"},
}


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _navigate_desc or ""}
)
def navigate(state, url: str) -> dict:
    """Navigate to URL.

    Args:
        url: URL to navigate to

    Returns:
        Navigation result in markdown
    """
    if error := check_connection(state):
        return error

    try:
        response = state.client.navigate(url)
        result = response.get("result", {})
    except Exception as e:
        return error_response(f"Navigation failed: {e}")

    return info_response(
        title="Navigation",
        fields={
            "URL": url,
            "Frame ID": result.get("frameId", "None"),
            "Loader ID": result.get("loaderId", "None"),
        },
    )


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _reload_desc or ""}
)
def reload(state, ignore_cache: bool = False) -> dict:
    """Reload the current page.

    Args:
        ignore_cache: Force reload ignoring cache

    Returns:
        Reload status in markdown
    """
    if error := check_connection(state):
        return error

    try:
        state.client.reload_page(ignore_cache)
    except Exception as e:
        return error_response(f"Reload failed: {e}")

    return info_response(
        title="Page Reload", fields={"Status": "Page reloaded", "Cache": "Ignored" if ignore_cache else "Used"}
    )


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _back_desc or ""}
)
def back(state) -> dict:
    """Navigate back in history.

    Returns:
        Navigation result in markdown
    """
    if error := check_connection(state):
        return error

    try:
        # Get history
        response = state.client.get_navigation_history()
        history = response.get("result", {})
        entries = history.get("entries", [])
        current_index = history.get("currentIndex", 0)

        if current_index > 0:
            # Navigate to previous entry
            target_id = entries[current_index - 1]["id"]
            state.client.navigate_to_history_entry(target_id)

            prev_entry = entries[current_index - 1]
            return info_response(
                title="Navigation Back",
                fields={
                    "Status": "Navigated back",
                    "Page": prev_entry.get("title", "Untitled"),
                    "URL": prev_entry.get("url", ""),  # Full URL, no truncation
                    "Index": f"{current_index - 1} of {len(entries) - 1}",
                },
            )

        return error_response("No history to go back")
    except Exception as e:
        return error_response(f"Navigation failed: {e}")


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _forward_desc or ""}
)
def forward(state) -> dict:
    """Navigate forward in history.

    Returns:
        Navigation result in markdown
    """
    if error := check_connection(state):
        return error

    try:
        # Get history
        response = state.client.get_navigation_history()
        history = response.get("result", {})
        entries = history.get("entries", [])
        current_index = history.get("currentIndex", 0)

        if current_index < len(entries) - 1:
            # Navigate to next entry
            target_id = entries[current_index + 1]["id"]
            state.client.navigate_to_history_entry(target_id)

            next_entry = entries[current_index + 1]
            return info_response(
                title="Navigation Forward",
                fields={
                    "Status": "Navigated forward",
                    "Page": next_entry.get("title", "Untitled"),
                    "URL": next_entry.get("url", ""),  # Full URL, no truncation
                    "Index": f"{current_index + 1} of {len(entries) - 1}",
                },
            )

        return error_response("No history to go forward")
    except Exception as e:
        return error_response(f"Navigation failed: {e}")


@app.command(display="markdown", fastmcp={"type": "resource", "mime_type": "text/markdown"})
def page(state) -> dict:
    """Get current page information.

    Returns:
        Current page information in markdown
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    try:
        # Get from navigation history
        response = state.client.get_navigation_history()
        history = response.get("result", {})
        entries = history.get("entries", [])
        current_index = history.get("currentIndex", 0)

        if entries and current_index < len(entries):
            current = entries[current_index]

            # Also get title from Runtime
            try:
                title_response = state.client.evaluate_js("document.title")
                title = title_response.get("result", {}).get("result", {}).get("value", current.get("title", ""))
            except Exception:
                title = current.get("title", "")

            # Get tips from TIPS.md
            tips = get_tips("page")

            # Build formatted response
            return info_response(
                title=title or "Untitled Page",
                fields={
                    "URL": current.get("url", ""),  # Full URL
                    "ID": current.get("id", ""),
                    "Type": current.get("transitionType", ""),
                },
                tips=tips,
            )

        return error_response("No navigation history available")
    except Exception as e:
        return error_response(f"Failed to get page info: {e}")


@app.command(
    display="markdown",
    fastmcp={"type": "resource", "mime_type": "text/markdown"},
)
def history(state, _ctx: ExecutionContext = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Get navigation history.

    Returns:
        Table of history entries with current marked
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    try:
        response = state.client.get_navigation_history()
        history_data = response.get("result", {})
        entries = history_data.get("entries", [])
        current_index = history_data.get("currentIndex", 0)

        # Format rows for table with FULL data
        rows = [
            {
                "Index": str(i),
                "Current": "Yes" if i == current_index else "",
                "Title": entry.get("title", ""),  # Full title
                "URL": entry.get("url", ""),  # Full URL
            }
            for i, entry in enumerate(entries)
        ]

        # Use mode-specific truncation
        is_repl = _ctx and _ctx.is_repl()
        truncate = _HISTORY_REPL_TRUNCATE if is_repl else _HISTORY_MCP_TRUNCATE

        # Build markdown response
        return table_response(
            title="Navigation History",
            headers=["Index", "Current", "Title", "URL"],
            rows=rows,
            summary=f"{len(entries)} entries, current index: {current_index}",
            truncate=truncate,
        )
    except Exception as e:
        return error_response(f"Failed to get history: {e}")
