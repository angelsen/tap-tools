"""Dynamic CDP query builder with field discovery.

PUBLIC API:
  - build_query: Build SQL queries with automatic field discovery
"""


def build_query(
    session, query: dict, event_type: str | list[str] | None = None, limit: int = 20
) -> tuple[str, dict[str, list[str]]]:
    """Build SQL queries with automatic CDP field discovery.

    Uses CDPSession's live field_paths lookup built from actual events.
    Supports filtering, wildcard matching, and multi-field extraction.

    Args:
        session: CDPSession with field_paths lookup.
        query: Field names and values - "*" extracts only, values filter.
        event_type: Optional CDP event type(s) to filter.
        limit: Maximum results. Defaults to 20.

    Returns:
        Tuple of (sql_query, discovered_fields_dict).

    Examples:
        build_query(session, {"url": "*"})  # Extract all URL fields
        build_query(session, {"status": 200})  # Filter by status=200
        build_query(session, {"url": "*youtube*", "status": 200})  # Multiple fields
    """

    # Field discovery using live field_paths
    discovered = {}
    for key in query.keys():
        if key in ["limit"]:
            continue
        discovered[key] = session.discover_field_paths(key)

    # Handle case where no fields found
    if not any(discovered.values()):
        return "SELECT NULL as no_fields_found FROM events LIMIT 0", discovered

    # Build WHERE conditions
    where_conditions = []

    # Filter by CDP event type
    if event_type:
        if isinstance(event_type, str):
            where_conditions.append(f"json_extract_string(event, '$.method') = '{event_type}'")
        elif isinstance(event_type, list):
            types_str = ", ".join(f"'{t}'" for t in event_type)
            where_conditions.append(f"json_extract_string(event, '$.method') IN ({types_str})")

    # Build field filters using discovered paths
    for key, value in query.items():
        if key in ["limit"] or value == "*":
            continue

        paths = discovered.get(key, [])
        if not paths:
            continue

        # Create filter conditions for each path
        path_conditions = []
        for path in paths:
            # Remove event type prefix for JSON path
            actual_path = path.split(":", 1)[1] if ":" in path else path
            json_path = "$." + actual_path

            if isinstance(value, str):
                # Convert wildcards to SQL LIKE patterns
                if "*" in value or "?" in value:
                    pattern = value.replace("*", "%").replace("?", "_")
                else:
                    pattern = value
                path_conditions.append(f"json_extract_string(event, '{json_path}') LIKE '{pattern}'")
            elif isinstance(value, (int, float)):
                # Use string comparison for numeric values to avoid type conversion errors
                path_conditions.append(f"json_extract_string(event, '{json_path}') = '{value}'")
            elif isinstance(value, bool):
                path_conditions.append(f"json_extract_string(event, '{json_path}') = '{str(value).lower()}'")
            elif value is None:
                path_conditions.append(f"json_extract_string(event, '{json_path}') IS NULL")

        # OR conditions between different paths for same field
        if path_conditions:
            if len(path_conditions) == 1:
                where_conditions.append(path_conditions[0])
            else:
                where_conditions.append(f"({' OR '.join(path_conditions)})")

    # Build SELECT clause with rowid and discovered fields
    select_parts = ["rowid"]
    for key, paths in discovered.items():
        for path in paths:
            # Use actual path for JSON, full path for column alias
            actual_path = path.split(":", 1)[1] if ":" in path else path
            json_path = "$." + actual_path
            select_parts.append(f"json_extract_string(event, '{json_path}') as \"{path}\"")

    # Assemble final SQL query
    sql = f"SELECT {', '.join(select_parts)} FROM events"

    if where_conditions:
        sql += " WHERE " + " AND ".join(where_conditions)

    sql += f" ORDER BY rowid DESC LIMIT {limit}"

    return sql, discovered
