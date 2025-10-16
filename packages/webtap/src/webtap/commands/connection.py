"""Chrome browser connection management commands."""

from webtap.app import app
from webtap.commands._builders import check_connection, info_response, table_response, error_response
from webtap.commands._tips import get_tips


@app.command(display="markdown", fastmcp={"type": "tool"})
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
    if page is not None and page_id is not None:
        return error_response("Cannot specify both 'page' and 'page_id'. Use one or the other.")

    result = state.service.connect_to_page(page_index=page, page_id=page_id)

    if "error" in result:
        return error_response(result["error"])

    # Success - return formatted info with full URL
    return info_response(
        title="Connection Established",
        fields={"Page": result["title"], "URL": result["url"]},  # Full URL
    )


@app.command(display="markdown", fastmcp={"type": "tool"})
def disconnect(state) -> dict:
    """Disconnect from Chrome."""
    result = state.service.disconnect()

    if not result["was_connected"]:
        return info_response(title="Disconnect Status", fields={"Status": "Not connected"})

    return info_response(title="Disconnect Status", fields={"Status": "Disconnected"})


@app.command(display="markdown", fastmcp={"type": "tool"})
def clear(state, events: bool = True, console: bool = False, cache: bool = False) -> dict:
    """Clear various data stores.

    Args:
        events: Clear CDP events (default: True)
        console: Clear console messages (default: False)
        cache: Clear body cache (default: False)

    Examples:
        clear()                                    # Clear events only
        clear(events=True, console=True)          # Clear events and console
        clear(cache=True)                          # Clear cache only
        clear(events=False, console=True)         # Console only
        clear(events=True, console=True, cache=True)  # Clear everything

    Returns:
        Summary of what was cleared
    """

    cleared = []

    # Clear CDP events
    if events:
        state.service.clear_events()
        cleared.append("events")

    # Clear browser console
    if console:
        if state.cdp and state.cdp.is_connected:
            if state.service.console.clear_browser_console():
                cleared.append("console")
        else:
            cleared.append("console (not connected)")

    # Clear body cache
    if cache:
        if hasattr(state.service, "body") and state.service.body:
            count = state.service.body.clear_cache()
            cleared.append(f"cache ({count} bodies)")
        else:
            cleared.append("cache (0 bodies)")

    # Return summary
    if not cleared:
        return info_response(
            title="Clear Status",
            fields={"Result": "Nothing to clear (specify events=True, console=True, or cache=True)"},
        )

    return info_response(title="Clear Status", fields={"Cleared": ", ".join(cleared)})


@app.command(
    display="markdown",
    truncate={
        "Title": {"max": 20, "mode": "end"},
        "URL": {"max": 30, "mode": "middle"},
        "ID": {"max": 6, "mode": "end"},
    },
    fastmcp={"type": "resource", "mime_type": "application/json"},
)
def pages(state) -> dict:
    """List available Chrome pages.

    Returns:
        Table of available pages in markdown
    """
    result = state.service.list_pages()
    pages_list = result.get("pages", [])

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

    # Build markdown response
    return table_response(
        title="Chrome Pages",
        headers=["Index", "Title", "URL", "ID", "Connected"],
        rows=rows,
        summary=f"{len(pages_list)} page{'s' if len(pages_list) != 1 else ''} available",
        warnings=warnings if warnings else None,
        tips=tips,
    )


@app.command(display="markdown", fastmcp={"type": "resource", "mime_type": "application/json"})
def status(state) -> dict:
    """Get connection status.

    Returns:
        Status information in markdown
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    status = state.service.get_status()

    # Build formatted response with full URL
    return info_response(
        title="Connection Status",
        fields={
            "Page": status.get("title", "Unknown"),
            "URL": status.get("url", ""),  # Full URL
            "Events": f"{status['events']} stored",
            "Fetch": "Enabled" if status["fetch_enabled"] else "Disabled",
            "Domains": ", ".join(status["enabled_domains"]),
        },
    )
