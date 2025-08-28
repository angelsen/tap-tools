"""Console monitoring commands."""

from webtap.app import app
from webtap.cdp.helpers import build_console_row


@app.command(display="table", headers=["Time", "Level", "Message", "Source"])
def console(state, id: str | None = None, limit: int = 20):
    """Show console messages.

    Args:
        id: Message ID for detail view (returns raw)
        limit: Max number of messages to show in table

    Returns:
        Table of messages or raw detail for single message
    """
    if not state.cdp.connected.is_set():
        return []

    # Build rows from all console events
    rows = []
    for event in state.cdp.console_events:
        row = build_console_row(event)
        rows.append(row)

    # Single item detail - return raw
    if id:
        for row in rows:
            if row["id"] == id or row["id"].startswith(id):  # Allow partial ID match
                # Return the full CDP event
                console.__display__ = None  # pyright: ignore[reportFunctionMemberAccess]
                return row["_event"]

        console.__display__ = None  # pyright: ignore[reportFunctionMemberAccess]
        return {"error": f"Console message {id} not found"}

    # Table view - newest first (console_events is a deque, newest at end)
    rows.reverse()

    # Format for table display
    table_rows = []
    for row in rows[:limit]:
        # Format timestamp for display
        try:
            timestamp = float(row["id"]) if row["id"].replace(".", "").isdigit() else 0
            time_str = f"{timestamp:.2f}" if timestamp else "-"
        except (ValueError, AttributeError):
            time_str = "-"

        table_rows.append(
            {
                "Time": time_str,
                "Level": row["level"].upper(),
                "Message": row["message"][:80] + "..." if len(row["message"]) > 80 else row["message"],
                "Source": row["source"],
            }
        )

    return table_rows


@app.command()
def clear_console(state):
    """Clear console events.

    Returns:
        Clear status
    """
    if not state.cdp.connected.is_set():
        return "Not connected"

    count = len(state.cdp.console_events)
    state.cdp.console_events.clear()

    # Also clear browser console
    try:
        state.cdp.execute("Runtime.discardConsoleEntries")
    except Exception:
        pass  # Not critical if this fails

    return f"Cleared {count} console messages"
