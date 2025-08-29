"""General CDP event querying with dynamic field discovery."""

from webtap.app import app
from webtap.cdp.query import build_query
from webtap.commands._utils import (
    process_query_results_for_table,
    truncate_string
)


@app.command(display="table", headers=["ID", "Field", "Value"])
def events(state, limit: int = 20, max_width: int = 80, **fields):
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
        Table with discovered fields and values, cacheable IDs
    """
    if not state.cdp or not state.cdp.is_connected:
        return []
    
    # Build query with dynamic field discovery
    query = {**fields}
    if "limit" in query:
        limit = query.pop("limit")
    
    sql, discovered = build_query(
        state.cdp,
        query,
        event_type=None,  # Search ALL event types
        limit=limit
    )
    
    # Execute query
    results = state.cdp.query(sql)
    
    # Process results into field-value pairs
    field_value_pairs = process_query_results_for_table(results, discovered)
    
    # Clear event cache for fresh results
    state.cache_clear("event")
    
    # Build table rows with caching
    rows = []
    for field_path, value in field_value_pairs:
        # Cache the field:value pair
        cache_id = state.cache_add("event", (field_path, value))
        
        # Format value for display
        if isinstance(value, str):
            # Use middle truncation for URLs
            if any(x in field_path.lower() for x in ['url', 'referer', 'origin']):
                display_value = truncate_string(value, max_width, mode="middle")
            else:
                display_value = truncate_string(value, max_width)
        else:
            display_value = truncate_string(str(value), max_width)
        
        rows.append({
            "ID": cache_id,
            "Field": field_path,
            "Value": display_value
        })
    
    return rows




@app.command()
def inspect(state, event: str | None = None, **kwargs):
    """
    Inspect cached event data in detail.
    
    Args:
        event: Event ID from query results (e.g., "e1", "e2")
        
    Examples:
        events(url="*api*")    # Lists events with IDs
        inspect(event="e1")    # Show full details of event e1
        
    Returns:
        Detailed view of the cached event data
    """
    # Handle both positional and keyword argument
    event_id = event or kwargs.get("event")
    
    if not event_id:
        return "Usage: inspect(event='id'), e.g., inspect(event='e1')"
    
    # Check event cache
    cache = state.cache.get("event", {})
    if event_id not in cache:
        return f"Event value {event_id} not found. Run events() first to populate cache."
    
    # Return the cached data (stored as tuple)
    field, value = cache[event_id]
    
    # Format for display
    output = [f"{field}:"]
    
    # Pretty print if it's JSON-like
    import json
    try:
        if isinstance(value, str) and value.startswith(("{", "[")):
            parsed = json.loads(value)
            output.append(json.dumps(parsed, indent=2))
        else:
            output.append(str(value))
    except (json.JSONDecodeError, ValueError):
        output.append(str(value))
    
    return "\n".join(output)


@app.command()
def clear_events(state):
    """
    Clear all stored CDP events and field lookup.
    
    Returns:
        Confirmation message
    """
    if not state.cdp:
        return "Not connected"
    
    state.cdp.clear_events()
    state.cache.get("event", {}).clear()
    
    return "Events cleared"