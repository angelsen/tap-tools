"""Browser navigation commands."""

from webtap.app import app


@app.command()
def navigate(state, url: str) -> dict:
    """Navigate to URL.

    Args:
        url: URL to navigate to

    Returns:
        Navigation result from CDP
    """
    if not state.cdp.connected.is_set():
        raise RuntimeError("Not connected")

    return state.cdp.execute("Page.navigate", {"url": url})


@app.command()
def reload(state, ignore_cache: bool = False) -> dict:
    """Reload the current page.

    Args:
        ignore_cache: Force reload ignoring cache

    Returns:
        CDP response
    """
    if not state.cdp.connected.is_set():
        raise RuntimeError("Not connected")

    return state.cdp.execute("Page.reload", {"ignoreCache": ignore_cache})


@app.command()
def back(state) -> dict:
    """Navigate back in history.

    Returns:
        Navigation history with current entry
    """
    if not state.cdp.connected.is_set():
        raise RuntimeError("Not connected")

    # Get history
    history = state.cdp.execute("Page.getNavigationHistory")
    entries = history.get("entries", [])
    current_index = history.get("currentIndex", 0)

    if current_index > 0:
        # Navigate to previous entry
        target_id = entries[current_index - 1]["id"]
        state.cdp.execute("Page.navigateToHistoryEntry", {"entryId": target_id})
        return {"navigated": True, "index": current_index - 1}

    return {"navigated": False, "reason": "No history to go back"}


@app.command()
def forward(state) -> dict:
    """Navigate forward in history.

    Returns:
        Navigation result
    """
    if not state.cdp.connected.is_set():
        raise RuntimeError("Not connected")

    # Get history
    history = state.cdp.execute("Page.getNavigationHistory")
    entries = history.get("entries", [])
    current_index = history.get("currentIndex", 0)

    if current_index < len(entries) - 1:
        # Navigate to next entry
        target_id = entries[current_index + 1]["id"]
        state.cdp.execute("Page.navigateToHistoryEntry", {"entryId": target_id})
        return {"navigated": True, "index": current_index + 1}

    return {"navigated": False, "reason": "No history to go forward"}


@app.command(display="markdown")
def page(state) -> dict:
    """Get current page information.

    Returns:
        Current page information in markdown
    """
    if not state.cdp.connected.is_set():
        raise RuntimeError("Not connected")

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

        # Return markdown format
        return {
            "elements": [
                {"type": "heading", "content": title, "level": 1},
                {"type": "text", "content": current.get("url", "")},
                {
                    "type": "code_block",
                    "content": f"ID: {current.get('id')}\nType: {current.get('transitionType', '')}",
                    "language": "",
                },
            ]
        }

    return {"elements": [{"type": "text", "content": "No navigation history"}]}


@app.command(display="table", headers=["Index", "Current", "Title", "URL"])
def history(state) -> list[dict]:
    """Get navigation history.

    Returns:
        Table of history entries with current marked
    """
    if not state.cdp.connected.is_set():
        raise RuntimeError("Not connected")

    history = state.cdp.execute("Page.getNavigationHistory")
    entries = history.get("entries", [])
    current_index = history.get("currentIndex", 0)

    # Format for table display
    return [
        {
            "Index": str(i),
            "Current": "→" if i == current_index else "",
            "Title": entry.get("title", "")[:40] + "..."
            if len(entry.get("title", "")) > 40
            else entry.get("title", ""),
            "URL": entry.get("url", "")[:50] + "..." if len(entry.get("url", "")) > 50 else entry.get("url", ""),
        }
        for i, entry in enumerate(entries)
    ]
