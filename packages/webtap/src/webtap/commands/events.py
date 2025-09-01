"""CDP event querying with dynamic field discovery.

PUBLIC API:
  - events: Query any CDP events by field values with automatic discovery
"""

from webtap.app import app
from webtap.cdp import build_query
from webtap.commands._errors import check_connection
from webtap.commands._utils import process_events_query_results, build_table_response


@app.command(display="markdown")
def events(state, limit: int = 20, max_width: int = 80, **fields) -> dict:
    """
    Query any CDP events by field values with automatic discovery.

    Searches across ALL event types - network, console, page, etc.
    Field names are discovered automatically and case-insensitive.

    Args:
        limit: Maximum results (default: 20)
        max_width: Max column width for display (default: 80)
        **fields: Field names and values to search/extract
                 - "*" means extract only (no filter)
                 - Specific value means filter AND extract

    Examples:
        events(url="*api*")                  # Find all API calls
        events(status=200)                    # Find successful responses
        events(method="POST", url="*login*") # POST requests to login
        events(level="error")                # Console errors
        events(type="Document")              # Page navigations
        events(headers="*")                  # Extract all header fields

    Returns:
        Table showing rowid and extracted field values in markdown
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    # Build query using the query module with fuzzy field discovery
    sql, discovered_fields = build_query(state.cdp, fields, limit=limit)

    # If no fields discovered, return empty
    if not discovered_fields or not any(discovered_fields.values()):
        return build_table_response(
            title="Event Query Results", headers=["ID", "Field", "Value"], rows=[], summary="No matching fields found"
        )

    # Execute query
    results = state.cdp.query(sql)

    # Process results into display rows - no caching needed!
    rows = process_events_query_results(results, discovered_fields, max_width)

    # Build warnings if needed
    warnings = []
    if limit and len(results) == limit:
        warnings.append(f"Showing first {limit} results (use limit parameter to see more)")

    # Build markdown response
    return build_table_response(
        title="Event Query Results",
        headers=["ID", "Field", "Value"],
        rows=rows,
        summary=f"{len(rows)} field values from {len(results)} events",
        warnings=warnings,
    )
