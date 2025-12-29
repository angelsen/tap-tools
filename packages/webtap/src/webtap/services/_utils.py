"""Service layer utilities.

Internal module - not part of PUBLIC API.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_nested(obj: dict | None, path: list[str], *, case_insensitive: bool = False) -> Any:
    """Get nested value from dict by path.

    Args:
        obj: Dictionary to traverse
        path: List of keys forming the path
        case_insensitive: If True, match keys case-insensitively (for HTTP headers)

    Returns:
        Value at path, or None if path doesn't exist
    """
    for key in path:
        if obj is None:
            return None
        if isinstance(obj, dict):
            if case_insensitive:
                matching_key = next((k for k in obj.keys() if k.lower() == key.lower()), None)
                if matching_key:
                    obj = obj.get(matching_key)
                else:
                    return None
            else:
                obj = obj.get(key)
        else:
            return None
    return obj


def set_nested(result: dict, path: list[str], value: Any) -> None:
    """Set nested value in dict by path, creating intermediate dicts.

    Args:
        result: Dictionary to modify
        path: List of keys forming the path
        value: Value to set at the path
    """
    current = result
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[path[-1]] = value


def aggregate_query(
    cdps: list[Any],
    sql: str,
    params: list | None = None,
    *,
    error_context: str = "query",
) -> list[tuple]:
    """Execute SQL query across multiple CDPSessions, aggregate results.

    Args:
        cdps: List of CDPSession instances
        sql: SQL query to execute
        params: Optional query parameters
        error_context: Context string for error logging

    Returns:
        Aggregated list of result rows from all sessions
    """
    all_rows: list[tuple] = []
    for cdp in cdps:
        try:
            rows = cdp.query(sql, params) if params else cdp.query(sql)
            all_rows.extend(rows)
        except Exception as e:
            logger.warning(f"Failed to {error_context} from {cdp.target}: {e}")
    return all_rows
