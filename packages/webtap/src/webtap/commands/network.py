"""Network monitoring commands."""

from webtap.app import app
from webtap.commands._utils import (
    truncate_string,
    format_size,
    format_id
)
from webtap.commands.filters import get_filter_sql




@app.command(display="table", headers=["ID", "Method", "Status", "URL", "Type", "Size"])
def network(state, all_filters: bool = True, default_filter: bool = True, filters: list | None = None, limit: int = 20):
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
        Table of network requests
    """
    if not state.cdp or not state.cdp.is_connected:
        return []
        
    sql = """
    SELECT 
        json_extract_string(event, '$.params.requestId') as ID,
        COALESCE(
            json_extract_string(event, '$.params.request.method'),
            json_extract_string(event, '$.params.response.request.method'),
            'GET'
        ) as Method,
        json_extract_string(event, '$.params.response.status') as Status,
        COALESCE(
            json_extract_string(event, '$.params.response.url'),
            json_extract_string(event, '$.params.request.url')
        ) as URL,
        json_extract_string(event, '$.params.type') as Type,
        json_extract_string(event, '$.params.response.encodedDataLength') as Size
    FROM events 
    WHERE json_extract_string(event, '$.method') = 'Network.responseReceived'
    """
    
    # Build list of categories to apply
    categories_to_apply = []
    
    if all_filters:
        # Apply all defined filter categories
        if hasattr(state, 'filters'):
            categories_to_apply = list(state.filters.keys())
    else:
        # Apply specific filters
        if default_filter:
            categories_to_apply.append("default")
        if filters:
            categories_to_apply.extend(filters)
    
    # Apply all filter categories
    if categories_to_apply:
        filter_sql = get_filter_sql(categories_to_apply, state)
        if filter_sql:
            sql += filter_sql
    
    sql += f" ORDER BY rowid DESC LIMIT {limit}"
    
    # Execute query
    results = state.cdp.query(sql)
    
    # Format for table display
    rows = []
    for row in results:
        # Unpack tuple
        id_val, method, status, url, type_val, size = row
        
        rows.append({
            "ID": format_id(id_val),
            "Method": method or "GET",
            "Status": str(status) if status else "-",
            "URL": truncate_string(url, 60, mode="middle"),  # Middle truncation for URLs
            "Type": type_val or "-",
            "Size": format_size(size)
        })
    
    return rows


