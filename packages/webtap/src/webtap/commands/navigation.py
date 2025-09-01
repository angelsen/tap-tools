"""Browser navigation commands."""

from webtap.app import app
from webtap.commands._errors import check_connection, error_response
from webtap.commands._utils import build_info_response, build_table_response
from webtap.commands._symbols import sym


@app.command(display="markdown")
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

    return build_info_response(
        title="Navigation",
        fields={
            "URL": url,
            "Frame ID": result.get("frameId", sym("empty")),
            "Loader ID": result.get("loaderId", sym("empty")),
        },
    )


@app.command(display="markdown")
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

    return build_info_response(
        title="Page Reload", fields={"Status": "Page reloaded", "Cache": "Ignored" if ignore_cache else "Used"}
    )


@app.command(display="markdown")
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
        return build_info_response(
            title="Navigation Back",
            fields={
                "Status": "Navigated back",
                "Page": prev_entry.get("title", "Untitled"),
                "URL": prev_entry.get("url", ""),
                "Index": f"{current_index - 1} of {len(entries) - 1}",
            },
        )

    return error_response("custom", custom_message="No history to go back")


@app.command(display="markdown")
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
        return build_info_response(
            title="Navigation Forward",
            fields={
                "Status": "Navigated forward",
                "Page": next_entry.get("title", "Untitled"),
                "URL": next_entry.get("url", ""),
                "Index": f"{current_index + 1} of {len(entries) - 1}",
            },
        )

    return error_response("custom", custom_message="No history to go forward")


@app.command(display="markdown")
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

        # Build formatted response
        return build_info_response(
            title=title or "Untitled Page",
            fields={
                "URL": current.get("url", ""),
                "ID": current.get("id", ""),
                "Type": current.get("transitionType", ""),
            },
        )

    return error_response("no_data", custom_message="No navigation history available")


@app.command(display="markdown")
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

    # Format rows for table
    rows = [
        {
            "Index": str(i),
            "Current": sym("current") if i == current_index else "",
            "Title": entry.get("title", "")[:40] + "..."
            if len(entry.get("title", "")) > 40
            else entry.get("title", ""),
            "URL": entry.get("url", "")[:50] + "..." if len(entry.get("url", "")) > 50 else entry.get("url", ""),
        }
        for i, entry in enumerate(entries)
    ]

    # Build markdown response
    return build_table_response(
        title="Navigation History",
        headers=["Index", "Current", "Title", "URL"],
        rows=rows,
        summary=f"{len(entries)} entries, current index: {current_index}",
    )
