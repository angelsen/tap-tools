"""CDP query builder using live field lookup for filtering and extraction."""


def build_query(
    session,
    query: dict,
    event_type: str | list[str] | None = None,
    limit: int = 20
) -> tuple[str, dict[str, list[str]]]:
    """
    Build CDP queries with automatic field discovery, filtering, and extraction.
    
    Uses session's live field_paths lookup built from actual CDP events.
    Both filtering and extraction use the same discovered paths.
    
    Args:
        session: CDPSession with field_paths lookup
        query: Dict with field names and values
               - "*" means extract only (no filter)
               - Specific value means filter AND extract
        event_type: Optional CDP event type(s) to filter
        limit: Maximum results
        
    Returns:
        (sql_query, discovered_fields)
        discovered_fields = {"url": ["params.response.url", "params.request.url"], ...}
    
    Examples:
        # Extract all url fields
        build_query(session, {"url": "*"})
        
        # Filter by status=200 and extract status fields
        build_query(session, {"status": 200})
        
        # Filter and extract multiple fields
        build_query(session, {"url": "*youtube*", "status": 200})
    """
    
    # Discovery - instant lookup from live field_paths
    discovered = {}
    for key in query.keys():
        if key in ["limit"]:
            continue
        discovered[key] = session.discover_field_paths(key)
    
    # Early return if no fields discovered
    if not any(discovered.values()):
        return "SELECT NULL as no_fields_found FROM events LIMIT 0", discovered
    
    # Build WHERE conditions
    where_conditions = []
    
    # Event type filter
    if event_type:
        if isinstance(event_type, str):
            where_conditions.append(f"json_extract_string(event, '$.method') = '{event_type}'")
        elif isinstance(event_type, list):
            types_str = ", ".join(f"'{t}'" for t in event_type)
            where_conditions.append(f"json_extract_string(event, '$.method') IN ({types_str})")
    
    # Field filters - use discovered paths with JSON extraction
    for key, value in query.items():
        if key in ["limit"] or value == "*":
            continue
            
        paths = discovered.get(key, [])
        if not paths:
            continue
        
        # Build filter conditions using full paths
        path_conditions = []
        for path in paths:
            # Extract actual path (remove event type prefix if present)
            actual_path = path.split(":", 1)[1] if ":" in path else path
            json_path = "$." + actual_path
            
            if isinstance(value, str):
                # Handle wildcards
                if "*" in value or "?" in value:
                    pattern = value.replace("*", "%").replace("?", "_")
                else:
                    pattern = value
                path_conditions.append(
                    f"json_extract_string(event, '{json_path}') LIKE '{pattern}'"
                )
            elif isinstance(value, (int, float)):
                path_conditions.append(
                    f"CAST(json_extract_string(event, '{json_path}') AS NUMERIC) = {value}"
                )
            elif isinstance(value, bool):
                path_conditions.append(
                    f"json_extract_string(event, '{json_path}') = '{str(value).lower()}'"
                )
            elif value is None:
                path_conditions.append(
                    f"json_extract_string(event, '{json_path}') IS NULL"
                )
        
        # OR between different paths for same field
        if path_conditions:
            if len(path_conditions) == 1:
                where_conditions.append(path_conditions[0])
            else:
                where_conditions.append(f"({' OR '.join(path_conditions)})")
    
    # Build SELECT with discovered paths
    select_parts = []
    for key, paths in discovered.items():
        for path in paths:
            # Extract actual path for SQL, but keep full path for alias
            actual_path = path.split(":", 1)[1] if ":" in path else path
            json_path = "$." + actual_path
            select_parts.append(
                f'json_extract_string(event, \'{json_path}\') as "{path}"'
            )
    
    # Construct final SQL
    if select_parts:
        sql = f"SELECT {', '.join(select_parts)} FROM events"
    else:
        sql = "SELECT * FROM events"
    
    if where_conditions:
        sql += " WHERE " + " AND ".join(where_conditions)
    
    sql += f" ORDER BY rowid DESC LIMIT {limit}"
    
    return sql, discovered