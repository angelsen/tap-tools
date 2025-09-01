"""Network monitoring commands."""

from webtap.app import app
from webtap.commands._errors import check_connection
from webtap.commands._utils import truncate_string, format_size, format_id, build_table_response
from webtap.commands._symbols import sym


@app.command(display="markdown")
def network(
    state, all_filters: bool = True, default_filter: bool = True, filters: list | None = None, limit: int = 20
) -> dict:
    """
    Show network requests in table format.

    Args:
        all_filters: Apply all defined filter categories (default: True)
        default_filter: Apply default filter category (default: True, ignored if all_filters=True)
        filters: Specific filter categories to apply (ignored if all_filters=True)
        limit: Max results (default: 20)

    Examples:
        network()                            # Apply all filters (default)
        network(all_filters=False)           # Just default filter
        network(all_filters=False, default_filter=False)  # Show everything
        network(all_filters=False, filters=["ads"])       # Default + ads only
        network(all_filters=False, default_filter=False, filters=["ads"])  # Only ads

    Note: Use filters() command to manage filter categories.
          Create a "default" category for the default filter.

    Returns:
        Table of network requests in markdown
    """
    # Check connection - return error dict if not connected
    if error := check_connection(state):
        return error

    # Get filter SQL from service
    if all_filters:
        # Use all enabled categories
        filter_sql = state.service.filters.get_filter_sql(use_all=True)
    elif filters or default_filter:
        # Build specific category list
        categories_to_apply = []
        if default_filter:
            categories_to_apply.append("default")
        if filters:
            categories_to_apply.extend(filters)
        filter_sql = state.service.filters.get_filter_sql(use_all=False, categories=categories_to_apply)
    else:
        # No filtering
        filter_sql = ""

    # Use NetworkService to get the data
    results = state.service.network.get_recent_requests(limit=limit, filter_sql=filter_sql)

    # Format for table display
    rows = []
    for row in results:
        # Unpack tuple - now includes rowid
        rowid, request_id, method, status, url, type_val, size = row

        rows.append(
            {
                "ID": str(rowid),
                "ReqID": format_id(request_id, 8),  # Truncate requestId for display
                "Method": method or "GET",
                "Status": str(status) if status else sym("empty"),
                "URL": truncate_string(url, 60, mode="middle"),  # Middle truncation for URLs
                "Type": type_val or sym("empty"),
                "Size": format_size(size),
            }
        )

    # Build warnings if needed
    warnings = []
    if limit and len(results) == limit:
        warnings.append(f"Showing first {limit} results (use limit parameter to see more)")

    # Build markdown response
    return build_table_response(
        title="Network Requests",
        headers=["ID", "ReqID", "Method", "Status", "URL", "Type", "Size"],
        rows=rows,
        summary=f"{len(rows)} requests",
        warnings=warnings,
    )
