"""Browser console message monitoring and display commands."""

from webtap.app import app
from webtap.commands._builders import check_connection, table_response
from webtap.commands._tips import get_tips


@app.command(
    display="markdown",
    truncate={"Message": {"max": 80, "mode": "end"}},
    transforms={"Time": "format_timestamp"},
    fastmcp={"type": "resource", "mime_type": "application/json"},
)
def console(state, limit: int = 50) -> dict:
    """Show console messages with full data.

    Args:
        limit: Max results (default: 50)

    Examples:
        console()           # Recent console messages
        console(limit=100)  # Show more messages

    Returns:
        Table of console messages with full data
    """
    # Check connection
    if error := check_connection(state):
        return error

    # Get data from service
    results = state.service.console.get_recent_messages(limit=limit)

    # Build rows with FULL data
    rows = []
    for row in results:
        rowid, level, source, message, timestamp = row
        rows.append(
            {
                "ID": str(rowid),
                "Level": (level or "LOG").upper(),
                "Source": source or "console",
                "Message": message or "",  # Full message
                "Time": timestamp or 0,  # Raw timestamp for transform
            }
        )

    # Build response
    warnings = []
    if limit and len(results) == limit:
        warnings.append(f"Showing first {limit} messages (use limit parameter to see more)")

    # Get contextual tips from TIPS.md
    tips = None
    if rows:
        # Focus on error/warning messages for debugging
        error_rows = [r for r in rows if r.get("Level", "").upper() in ["ERROR", "WARN", "WARNING"]]
        example_id = error_rows[0]["ID"] if error_rows else rows[0]["ID"]
        tips = get_tips("console", context={"id": example_id})

    return table_response(
        title="Console Messages",
        headers=["ID", "Level", "Source", "Message", "Time"],
        rows=rows,
        summary=f"{len(rows)} messages",
        warnings=warnings,
        tips=tips,
    )
