"""Browser page navigation and history commands."""

from webtap.app import app
from webtap.commands._builders import check_connection, info_response, table_response, error_response
from webtap.commands._tips import get_tips


@app.command(display="markdown", fastmcp={"type": "tool"})
def navigate(state, url: str) -> dict:
    """Navigate to URL.

    Args:
        url: URL to navigate to

    Returns:
        Navigation result in markdown
    """
    if error := check_connection(state):
        return error

    result = state.cdp.execute("Page.navigate", {"url": url})

    return info_response(
        title="Navigation",
        fields={
            "URL": url,
            "Frame ID": result.get("frameId", "None"),
            "Loader ID": result.get("loaderId", "None"),
        },
    )


@app.command(display="markdown", fastmcp={"type": "tool"})
def reload(state, ignore_cache: bool = False) -> dict:
    """Reload the current page.

    Args:
        ignore_cache: Force reload ignoring cache

    Returns:
        Reload status in markdown
    """
    if error := check_connection(state):
        return error

    state.cdp.execute("Page.reload", {"ignoreCache": ignore_cache})

    return info_response(
        title="Page Reload", fields={"Status": "Page reloaded", "Cache": "Ignored" if ignore_cache else "Used"}
    )


@app.command(display="markdown", fastmcp={"type": "tool"})
def back(state) -> dict:
    """Navigate back in history.

    Returns:
        Navigation result in markdown
    """
    if error := check_connection(state):
        return error

    # Get history
    history = state.cdp.execute("Page.getNavigationHistory")
    entries = history.get("entries", [])
    current_index = history.get("currentIndex", 0)

    if current_index > 0:
        # Navigate to previous entry
        target_id = entries[current_index - 1]["id"]
        state.cdp.execute("Page.navigateToHistoryEntry", {"entryId": target_id})

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


@app.command(display="markdown", fastmcp={"type": "tool"})
def forward(state) -> dict:
    """Navigate forward in history.

    Returns:
        Navigation result in markdown
    """
    if error := check_connection(state):
        return error

    # Get history
    history = state.cdp.execute("Page.getNavigationHistory")
    entries = history.get("entries", [])
    current_index = history.get("currentIndex", 0)

    if current_index < len(entries) - 1:
        # Navigate to next entry
        target_id = entries[current_index + 1]["id"]
        state.cdp.execute("Page.navigateToHistoryEntry", {"entryId": target_id})

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


@app.command(display="markdown", fastmcp={"type": "resource", "mime_type": "application/json"})
def page(state) -> dict:
    """Get current page information.

    Returns:
        Current page information in markdown
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    # Get from navigation history
    history = state.cdp.execute("Page.getNavigationHistory")
    entries = history.get("entries", [])
    current_index = history.get("currentIndex", 0)

    if entries and current_index < len(entries):
        current = entries[current_index]

        # Also get title from Runtime
        try:
            title = (
                state.cdp.execute("Runtime.evaluate", {"expression": "document.title", "returnByValue": True})
                .get("result", {})
                .get("value", current.get("title", ""))
            )
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


@app.command(
    display="markdown",
    truncate={"Title": {"max": 40, "mode": "end"}, "URL": {"max": 50, "mode": "middle"}},
    fastmcp={"type": "resource", "mime_type": "application/json"},
)
def history(state) -> dict:
    """Get navigation history.

    Returns:
        Table of history entries with current marked
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    history = state.cdp.execute("Page.getNavigationHistory")
    entries = history.get("entries", [])
    current_index = history.get("currentIndex", 0)

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

    # Build markdown response
    return table_response(
        title="Navigation History",
        headers=["Index", "Current", "Title", "URL"],
        rows=rows,
        summary=f"{len(entries)} entries, current index: {current_index}",
    )
