"""Browser console message monitoring and display commands.

PUBLIC API:
  - console: Show console messages in table format
"""

from webtap.app import app
from webtap.commands._errors import check_connection
from webtap.commands._utils import truncate_string, build_table_response
from webtap.commands._symbols import sym


@app.command(display="markdown")
def console(state, limit: int = 50) -> dict:
    """
    Show console messages in table format.

    Args:
        limit: Max results (default: 50)

    Examples:
        console()           # Recent console messages
        console(limit=100)  # Show more messages

    Returns:
        Table of console messages in markdown
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    # Use ConsoleService to get the data
    results = state.service.console.get_recent_messages(limit=limit)

    # Format for table display
    rows = []
    for row in results:
        rowid, level, source, message, timestamp = row
        rows.append(
            {
                "ID": str(rowid),
                "Level": (level or "log").upper(),
                "Source": source or "console",
                "Message": truncate_string(message, 80),
                "Time": timestamp[:19] if timestamp else sym("empty"),  # Just date and time
            }
        )

    # Build warnings if needed
    warnings = []
    if limit and len(results) == limit:
        warnings.append(f"Showing first {limit} messages (use limit parameter to see more)")

    # Build markdown response
    return build_table_response(
        title="Console Messages",
        headers=["ID", "Level", "Source", "Message", "Time"],
        rows=rows,
        summary=f"{len(rows)} messages",
        warnings=warnings,
    )
