"""Chrome browser connection management commands.

PUBLIC API:
  - connect: Connect to Chrome page and enable all required domains
  - disconnect: Disconnect from Chrome
  - clear: Clear various data stores (events, console, cache)
  - pages: List available Chrome pages
  - status: Get connection status
"""

from webtap.app import app
from webtap.commands._errors import check_connection, error_response
from webtap.commands._utils import build_info_response, build_table_response
from webtap.commands._symbols import sym


@app.command(display="markdown")
def connect(state, page: int | None = None, page_id: str | None = None) -> dict:
    """Connect to Chrome page and enable all required domains.

    Args:
        page: Page index to connect to (default: 0)
        page_id: Page ID to connect to (for stable reconnection)

    Returns:
        Connection status in markdown
    """
    result = state.service.connect_to_page(page_index=page, page_id=page_id)

    if "error" in result:
        return error_response("custom", custom_message=result["error"])

    # Success - return formatted info
    return build_info_response(title="Connection Established", fields={"Page": result["title"], "URL": result["url"]})


@app.command(display="markdown")
def disconnect(state) -> dict:
    """Disconnect from Chrome."""
    result = state.service.disconnect()

    if not result["was_connected"]:
        return build_info_response(title="Disconnect Status", fields={"Status": "Not connected"})

    return build_info_response(title="Disconnect Status", fields={"Status": "Disconnected"})


@app.command(display="markdown")
def clear(state, events: bool = True, console: bool = False, cache: bool = False) -> dict:
    """Clear various data stores.

    Args:
        events: Clear CDP events from DuckDB (default: True)
        console: Clear browser console (default: False)
        cache: Clear response body cache (default: False)

    Examples:
        clear()                                    # Clear events only (default)
        clear(console=True)                        # Clear console only
        clear(events=False, console=True)          # Clear console only (explicit)
        clear(events=True, console=True)           # Clear both
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
        return build_info_response(
            title="Clear Status",
            fields={"Result": "Nothing to clear (specify events=True, console=True, or cache=True)"},
        )

    return build_info_response(title="Clear Status", fields={"Cleared": ", ".join(cleared)})


@app.command(display="markdown")
def pages(state) -> dict:
    """List available Chrome pages.

    Returns:
        Table of available pages in markdown
    """
    result = state.service.list_pages()
    pages_list = result.get("pages", [])

    # Format rows for table
    rows = [
        {
            "Index": str(i),
            "Title": p.get("title", "Untitled")[:30] + "..."
            if len(p.get("title", "")) > 30
            else p.get("title", "Untitled"),
            "URL": p.get("url", "")[:40] + "..." if len(p.get("url", "")) > 40 else p.get("url", ""),
            "ID": p.get("id", "")[:8] + "...",  # Show first 8 chars of ID
            "Connected": sym("connected") if p.get("is_connected") else sym("disconnected"),
        }
        for i, p in enumerate(pages_list)
    ]

    # Build markdown response
    return build_table_response(
        title="Chrome Pages",
        headers=["Index", "Title", "URL", "ID", "Connected"],
        rows=rows,
        summary=f"{len(pages_list)} page{'s' if len(pages_list) != 1 else ''} available",
    )


@app.command(display="markdown")
def status(state) -> dict:
    """Get connection status.

    Returns:
        Status information in markdown
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    status = state.service.get_status()

    # Build formatted response
    return build_info_response(
        title="Connection Status",
        fields={
            "Page": status.get("title", "Unknown"),
            "URL": status.get("url", ""),
            "Events": f"{status['events']} stored",
            "Fetch": "Enabled" if status["fetch_enabled"] else "Disabled",
            "Domains": ", ".join(status["enabled_domains"]),
        },
    )
