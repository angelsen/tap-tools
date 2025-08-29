"""Filter management for network requests."""

import json
from pathlib import Path
from typing import Dict, Any

from webtap.app import app


def _get_filter_path() -> Path:
    """Get the path to the filter config file."""
    return Path.cwd() / ".webtap" / "filters.json"


@app.command()
def filters(state, add: Dict[str, str] | None = None, remove: Dict[str, str] | None = None,
           update: Dict[str, Any] | None = None, delete: Dict[str, str] | None = None,
           list: Dict[str, str] | None = None, save: bool = False, load: bool = False):
    """
    Manage network request filters in memory.
    
    Filters are kept in memory until explicitly saved to .webtap/filters.json.
    Create custom categories to organize your filters.
    
    Args:
        add: Add pattern {"domain": "*pattern*", "category": "ads"}
             or {"type": "Ping", "category": "tracking"}
        remove: Remove pattern {"domain": "*pattern*"} or {"type": "Ping"}
        update: Update category {"category": "ads", "domains": [...], "types": [...]}
        delete: Delete category {"category": "ads"}
        list: List specific category {"category": "ads"}
        save: Save current filters to .webtap/filters.json
        load: Load filters from .webtap/filters.json
        
    Examples:
        filters()                                              # List all filters
        filters(list={"category": "ads"})                     # List ads filters
        filters(add={"domain": "*doubleclick*", "category": "ads"})
        filters(add={"type": "Ping", "category": "tracking"})
        filters(remove={"domain": "*doubleclick*"})
        filters(update={"category": "ads", "domains": ["*google*", "*facebook*"]})
        filters(delete={"category": "ads"})
        filters(save=True)                                    # Persist to disk
        filters(load=True)                                    # Load from disk
        
    Returns:
        Current filter configuration or operation result
    """
    # Initialize filters in memory if not present
    if not hasattr(state, 'filters'):
        state.filters = {}
    
    filters = state.filters
    
    # Handle load operation
    if load:
        filter_path = _get_filter_path()
        if filter_path.exists():
            with open(filter_path, "r") as f:
                state.filters = json.load(f)
            return f"Loaded filters from {filter_path}"
        else:
            return f"No filter file found at {filter_path}"
    
    # Handle save operation
    if save:
        filter_path = _get_filter_path()
        filter_path.parent.mkdir(exist_ok=True)
        
        with open(filter_path, "w") as f:
            json.dump(filters, f, indent=2)
        return f"Saved filters to {filter_path}"
    
    # Handle add operation
    if add:
        category = add.get("category", "custom")
        if category not in filters:
            filters[category] = {"domains": [], "types": []}
        
        if "domain" in add:
            if add["domain"] not in filters[category]["domains"]:
                filters[category]["domains"].append(add["domain"])
                return f"Added domain pattern '{add['domain']}' to category '{category}'"
            return f"Domain pattern '{add['domain']}' already in category '{category}'"
        
        if "type" in add:
            if add["type"] not in filters[category]["types"]:
                filters[category]["types"].append(add["type"])
                return f"Added type '{add['type']}' to category '{category}'"
            return f"Type '{add['type']}' already in category '{category}'"
    
    # Handle remove operation
    elif remove:
        removed = False
        for category, config in filters.items():
            if "domain" in remove and remove["domain"] in config["domains"]:
                config["domains"].remove(remove["domain"])
                removed = True
                return f"Removed domain pattern '{remove['domain']}' from category '{category}'"
            
            if "type" in remove and remove["type"] in config["types"]:
                config["types"].remove(remove["type"])
                removed = True
                return f"Removed type '{remove['type']}' from category '{category}'"
        
        if not removed:
            return f"Pattern not found: {remove}"
    
    # Handle update operation
    elif update:
        category = update.get("category")
        if not category:
            return "Error: 'category' required for update"
        
        if category not in filters:
            filters[category] = {"domains": [], "types": []}
        
        if "domains" in update:
            filters[category]["domains"] = update["domains"]
        if "types" in update:
            filters[category]["types"] = update["types"]
        
        return f"Updated category '{category}'"
    
    # Handle delete operation
    elif delete:
        category = delete.get("category")
        if category in filters:
            del filters[category]
            return f"Deleted category '{category}'"
        return f"Category '{category}' not found"
    
    # Handle list operation
    if list:
        category = list.get("category")
        if category and category in filters:
            return {category: filters[category]}
        elif category:
            return f"Category '{category}' not found"
    
    # Default: return all filters (or empty dict if none)
    return filters if filters else "No filters defined. Use add={...} to create filters."


def get_filter_sql(categories: str | list[str] | None, state) -> str:
    """
    Get SQL WHERE conditions for filter categories.
    
    Used by network() command to apply filters.
    
    Args:
        categories: Single category name or list of categories
        state: App state (contains filters)
        
    Returns:
        SQL WHERE clause string
    """
    if not hasattr(state, 'filters'):
        return ""
    
    if not categories:
        return ""
    
    filters = state.filters
    if not filters:
        return ""
    
    # Handle single category or list
    if isinstance(categories, str):
        categories = [categories]
    
    conditions = []
    
    for category in categories:
        if category not in filters:
            continue
        
        config = filters[category]
        
        # Add type filters
        if config.get("types"):
            types_str = ", ".join(f"'{t}'" for t in config["types"])
            conditions.append(f"json_extract_string(event, '$.params.type') NOT IN ({types_str})")
        
        # Add domain filters
        for pattern in config.get("domains", []):
            # Convert wildcard to SQL LIKE pattern
            sql_pattern = pattern.replace("*", "%")
            # Use COALESCE to handle NULL values - if URL is NULL, treat as empty string
            conditions.append(f"COALESCE(json_extract_string(event, '$.params.response.url'), '') NOT LIKE '{sql_pattern}'")
            conditions.append(f"COALESCE(json_extract_string(event, '$.params.request.url'), '') NOT LIKE '{sql_pattern}'")
    
    if conditions:
        return " AND " + " AND ".join(conditions)
    return ""