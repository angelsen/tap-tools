"""Network request monitoring and display commands."""

from typing import List

from webtap.app import app
from webtap.commands._builders import check_connection, table_response
from webtap.commands._tips import get_tips


@app.command(
    display="markdown",
    truncate={"ReqID": {"max": 12, "mode": "end"}, "URL": {"max": 60, "mode": "middle"}},
    transforms={"Size": "format_size"},
    fastmcp=[{"type": "resource", "mime_type": "application/json"}, {"type": "tool"}],
)
def network(state, limit: int = 20, filters: List[str] = None, no_filters: bool = False) -> dict:  # pyright: ignore[reportArgumentType]
    """Show network requests with full data.

    As Resource (no parameters):
        network             # Returns last 20 requests with enabled filters

    As Tool (with parameters):
        network(limit=50)                    # More results
        network(filters=["ads"])            # Specific filter only
        network(no_filters=True, limit=50)  # Everything unfiltered

    Args:
        limit: Maximum results to show (default: 20)
        filters: Specific filter categories to apply
        no_filters: Show everything unfiltered (default: False)

    Returns:
        Table of network requests with full data
    """
    # Check connection
    if error := check_connection(state):
        return error

    # Get filter SQL from service
    if no_filters:
        filter_sql = ""
    elif filters:
        filter_sql = state.service.filters.get_filter_sql(use_all=False, categories=filters)
    else:
        filter_sql = state.service.filters.get_filter_sql(use_all=True)

    # Get data from service
    results = state.service.network.get_recent_requests(limit=limit, filter_sql=filter_sql)

    # Build rows with FULL data
    rows = []
    for row in results:
        rowid, request_id, method, status, url, type_val, size = row
        rows.append(
            {
                "ID": str(rowid),
                "ReqID": request_id or "",  # Full request ID
                "Method": method or "GET",
                "Status": str(status) if status else "-",
                "URL": url or "",  # Full URL
                "Type": type_val or "-",
                "Size": size or 0,  # Raw bytes
            }
        )

    # Build response with developer guidance
    warnings = []
    if limit and len(results) == limit:
        warnings.append(f"Showing first {limit} results (use limit parameter to see more)")

    # Get tips from TIPS.md with context, and add filter guidance
    combined_tips = [
        "Reduce noise with `filters()` - filter by type (XHR, Fetch) or domain (*/api/*)",
    ]

    if rows:
        example_id = rows[0]["ID"]
        context_tips = get_tips("network", context={"id": example_id})
        if context_tips:
            combined_tips.extend(context_tips)

    return table_response(
        title="Network Requests",
        headers=["ID", "ReqID", "Method", "Status", "URL", "Type", "Size"],
        rows=rows,
        summary=f"{len(rows)} requests" if rows else None,
        warnings=warnings,
        tips=combined_tips,
    )
