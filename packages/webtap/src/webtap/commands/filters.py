"""Network request filtering and categorization management commands."""

from webtap.app import app
from webtap.commands._builders import info_response, error_response


@app.command(display="markdown", fastmcp={"type": "tool"})
def filters(state, action: str = "list", config: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """
    Manage network request filters.

    Filters are managed by the service and can be persisted to .webtap/filters.json.

    Args:
        action: Filter operation
            - "list" - List all filter categories (default)
            - "show" - Show specific category details
            - "add" - Add patterns to category
            - "remove" - Remove patterns from category
            - "update" - Update entire category
            - "delete" - Delete entire category
            - "enable" - Enable category
            - "disable" - Disable category
            - "save" - Save filters to disk
            - "load" - Load filters from disk
        config: Action-specific configuration
            - For show: {"category": "ads"}
            - For add: {"category": "ads", "patterns": ["*ad*"], "type": "domain"}
            - For remove: {"patterns": ["*ad*"], "type": "domain"}
            - For update: {"category": "ads", "domains": [...], "types": [...]}
            - For delete/enable/disable: {"category": "ads"}

    Examples:
        filters()                                          # List all categories
        filters("list")                                    # Same as above
        filters("show", {"category": "ads"})              # Show ads category details
        filters("add", {"category": "ads",
                "patterns": ["*doubleclick*"]})           # Add domain pattern
        filters("add", {"category": "tracking",
                "patterns": ["Ping"], "type": "type"})    # Add type pattern
        filters("remove", {"patterns": ["*doubleclick*"]}) # Remove pattern
        filters("update", {"category": "ads",
                "domains": ["*google*", "*facebook*"]})   # Replace patterns
        filters("delete", {"category": "ads"})            # Delete category
        filters("save")                                   # Persist to disk
        filters("load")                                   # Load from disk

    Returns:
        Current filter configuration or operation result
    """
    fm = state.service.filters
    cfg = config or {}

    # Handle load operation
    if action == "load":
        if fm.load():
            # Convert display info to markdown
            display_info = fm.get_display_info()
            return {
                "elements": [
                    {"type": "heading", "content": "Filters Loaded", "level": 2},
                    {"type": "code_block", "content": display_info, "language": ""},
                ]
            }
        else:
            return error_response(f"No filters found at {fm.filter_path}")

    # Handle save operation
    elif action == "save":
        if fm.save():
            return info_response(
                title="Filters Saved", fields={"Categories": f"{len(fm.filters)}", "Path": str(fm.filter_path)}
            )
        else:
            return error_response("Failed to save filters")

    # Handle add operation
    elif action == "add":
        if not cfg:
            return error_response("Config required for add action")

        category = cfg.get("category", "custom")
        patterns = cfg.get("patterns", [])
        pattern_type = cfg.get("type", "domain")

        if not patterns:
            # Legacy single pattern support
            if pattern_type == "domain" and "domain" in cfg:
                patterns = [cfg["domain"]]
            elif pattern_type == "type" and "type" in cfg:
                patterns = [cfg["type"]]
            else:
                return error_response("Patterns required for add action")

        added = []
        failed = []
        for pattern in patterns:
            if fm.add_pattern(pattern, category, pattern_type):
                added.append(pattern)
            else:
                failed.append(pattern)

        if added and not failed:
            return info_response(
                title="Filter(s) Added",
                fields={
                    "Type": "Domain pattern" if pattern_type == "domain" else "Resource type",
                    "Patterns": ", ".join(added),
                    "Category": category,
                },
            )
        elif failed:
            return error_response(f"Pattern(s) already exist in category '{category}': {', '.join(failed)}")
        else:
            # This shouldn't happen unless patterns list was empty after all
            return error_response("No valid patterns provided")

    # Handle remove operation
    elif action == "remove":
        if not cfg:
            return error_response("Config required for remove action")

        patterns = cfg.get("patterns", [])
        pattern_type = cfg.get("type", "domain")

        if not patterns:
            return error_response("Patterns required for remove action")

        removed = []
        for pattern in patterns:
            category = fm.remove_pattern(pattern, pattern_type)
            if category:
                removed.append((pattern, category))

        if removed:
            return info_response(
                title="Filter(s) Removed",
                fields={
                    "Type": "Domain pattern" if pattern_type == "domain" else "Resource type",
                    "Removed": ", ".join(f"{p} from {c}" for p, c in removed),
                },
            )
        else:
            return error_response("Pattern(s) not found")

    # Handle update operation
    elif action == "update":
        if not cfg or "category" not in cfg:
            return error_response("'category' required for update action")

        category = cfg["category"]
        fm.update_category(category, domains=cfg.get("domains"), types=cfg.get("types"))
        return info_response(title="Category Updated", fields={"Category": category})

    # Handle delete operation
    elif action == "delete":
        if not cfg or "category" not in cfg:
            return error_response("'category' required for delete action")

        category = cfg["category"]
        if fm.delete_category(category):
            return info_response(title="Category Deleted", fields={"Category": category})
        return error_response(f"Category '{category}' not found")

    # Handle enable operation
    elif action == "enable":
        if not cfg or "category" not in cfg:
            return error_response("'category' required for enable action")

        category = cfg["category"]
        if category in fm.filters:
            fm.enabled_categories.add(category)
            return info_response(title="Category Enabled", fields={"Category": category})
        return error_response(f"Category '{category}' not found")

    # Handle disable operation
    elif action == "disable":
        if not cfg or "category" not in cfg:
            return error_response("'category' required for disable action")

        category = cfg["category"]
        if category in fm.filters:
            fm.enabled_categories.discard(category)
            return info_response(title="Category Disabled", fields={"Category": category})
        return error_response(f"Category '{category}' not found")

    # Handle show operation (specific category)
    elif action == "show":
        if not cfg or "category" not in cfg:
            return error_response("'category' required for show action")

        category = cfg["category"]
        if category in fm.filters:
            filters = fm.filters[category]
            enabled = "Enabled" if category in fm.enabled_categories else "Disabled"

            elements = [
                {"type": "heading", "content": f"Category: {category}", "level": 2},
                {"type": "text", "content": f"**Status:** {enabled}"},
            ]

            if filters.get("domains"):
                elements.append({"type": "text", "content": "**Domain Patterns:**"})
                elements.append({"type": "list", "items": filters["domains"]})

            if filters.get("types"):
                elements.append({"type": "text", "content": "**Resource Types:**"})
                elements.append({"type": "list", "items": filters["types"]})

            return {"elements": elements}
        return error_response(f"Category '{category}' not found")

    # Default list action: show all filters
    elif action == "list" or action == "":
        display_info = fm.get_display_info()
        return {
            "elements": [
                {"type": "heading", "content": "Filter Configuration", "level": 2},
                {"type": "code_block", "content": display_info, "language": ""},
            ]
        }

    else:
        return error_response(f"Unknown action: {action}")
