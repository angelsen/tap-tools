"""CDP event querying with dynamic field discovery."""

from webtap.app import app
from webtap.cdp import build_query
from webtap.commands._builders import check_connection, table_response
from webtap.commands._tips import get_tips, get_mcp_description


mcp_desc = get_mcp_description("events")


@app.command(
    display="markdown",
    truncate={
        "Value": {"max": 80, "mode": "end"}  # Only truncate values for display
    },
    fastmcp={"type": "tool", "description": mcp_desc} if mcp_desc else {"type": "tool"},
)
def events(state, filters: dict = None, limit: int = 20) -> dict:  # pyright: ignore[reportArgumentType]
    """
    Query CDP events by field values with automatic discovery.

    Searches across ALL event types - network, console, page, etc.
    Field names are discovered automatically and case-insensitive.

    Args:
        filters: Field filters to apply
            - {"method": "Network.*"} - Events matching pattern
            - {"status": 200, "method": "Network.responseReceived"}
            - {"url": "*"} - Extract field without filtering
        limit: Maximum results (default: 20)

    Examples:
        events()                                    # Recent 20 events
        events({"method": "Runtime.*"})            # Runtime events
        events({"requestId": "123"}, limit=100)    # Specific request
        events({"url": "*api*"})                   # Find all API calls
        events({"status": 200})                    # Find successful responses
        events({"method": "POST", "url": "*login*"}) # POST requests to login
        events({"level": "error"})                # Console errors
        events({"type": "Document"})              # Page navigations
        events({"headers": "*"})                  # Extract all header fields

    Returns:
        Table showing rowid and extracted field values in markdown
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    # Use filters dict, default to empty
    fields = filters or {}

    # Build query using the query module with fuzzy field discovery
    sql, discovered_fields = build_query(state.cdp, fields, limit=limit)

    # If no fields discovered, return empty
    if not discovered_fields or not any(discovered_fields.values()):
        return table_response(
            title="Event Query Results", headers=["ID", "Field", "Value"], rows=[], summary="No matching fields found"
        )

    # Execute query
    results = state.cdp.query(sql)

    # Process results into rows with FULL data
    rows = []
    for result_row in results:
        rowid = result_row[0]
        col_index = 1  # Skip rowid column

        for field_name, field_paths in discovered_fields.items():
            for field_path in field_paths:
                if col_index < len(result_row):
                    value = result_row[col_index]
                    if value is not None:
                        rows.append(
                            {
                                "ID": str(rowid),
                                "Field": field_path,
                                "Value": str(value),  # Full value, no truncation
                            }
                        )
                    col_index += 1

    # Build warnings if needed
    warnings = []
    if limit and len(results) == limit:
        warnings.append(f"Showing first {limit} results (use limit parameter to see more)")

    # Get tips from TIPS.md
    tips = None
    if rows:
        # Get unique event IDs for examples
        event_ids = list(set(row["ID"] for row in rows))[:1]
        if event_ids:
            example_id = event_ids[0]
            tips = get_tips("events", context={"id": example_id})

    # Build markdown response
    return table_response(
        title="Event Query Results",
        headers=["ID", "Field", "Value"],
        rows=rows,
        summary=f"{len(rows)} field values from {len(results)} events",
        warnings=warnings,
        tips=tips,
    )
