"""Network request filtering and categorization management commands."""

from webtap.app import app
from webtap.commands._builders import info_response, error_response


@app.command(display="markdown", fastmcp={"type": "tool"})
def filters(state, action: str = "list", config: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """
    Manage network request filters with include/exclude modes.

    CDP Types: Document, XHR, Fetch, Image, Stylesheet, Script, Font, Media, Other, Ping
    Domains filter URLs, types filter Chrome's resource loading mechanism.

    Actions:
        list: Show all categories (default)
        show: Display category - config: {"category": "api"}
        add: Add patterns - config: {"category": "api", "patterns": ["*api*"], "type": "domain", "mode": "include"}
        remove: Remove patterns - config: {"patterns": ["*api*"], "type": "domain"}
        update: Replace category - config: {"category": "api", "mode": "include", "domains": [...], "types": ["XHR", "Fetch"]}
        delete/enable/disable: Manage category - config: {"category": "api"}
        save/load: Persist to/from disk
    """
    fm = state.service.filters
    cfg = config or {}

    # Handle load operation
    if action == "load":
        if fm.load():
            # Build table data
            categories = fm.get_categories_summary()
            rows = []
            for cat in categories:
                mode = cat["mode"] or "exclude"
                mode_display = "include" if mode == "include" else "exclude"
                if cat["mode"] is None:
                    mode_display = "exclude*"  # Asterisk indicates missing mode field

                rows.append(
                    {
                        "Category": cat["name"],
                        "Status": "enabled" if cat["enabled"] else "disabled",
                        "Mode": mode_display,
                        "Domains": str(cat["domain_count"]),
                        "Types": str(cat["type_count"]),
                    }
                )

            elements = [
                {"type": "heading", "content": "Filters Loaded", "level": 2},
                {"type": "text", "content": f"From: `{fm.filter_path}`"},
                {"type": "table", "headers": ["Category", "Status", "Mode", "Domains", "Types"], "rows": rows},
            ]

            if any(cat["mode"] is None for cat in categories):
                elements.append({"type": "text", "content": "_* Mode not specified, defaulting to exclude_"})

            return {"elements": elements}
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
        mode = cfg.get("mode")  # Required, no default

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
        try:
            for pattern in patterns:
                if fm.add_pattern(pattern, category, pattern_type, mode):
                    added.append(pattern)
                else:
                    failed.append(pattern)
        except ValueError as e:
            return error_response(str(e))

        if added and not failed:
            return info_response(
                title="Filter(s) Added",
                fields={
                    "Type": "Domain pattern" if pattern_type == "domain" else "Resource type",
                    "Patterns": ", ".join(added),
                    "Category": category,
                    "Mode": mode,
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
        fm.update_category(category, domains=cfg.get("domains"), types=cfg.get("types"), mode=cfg.get("mode"))
        return info_response(
            title="Category Updated", fields={"Category": category, "Mode": cfg.get("mode", "exclude")}
        )

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
            mode = filters.get("mode", "exclude")

            elements = [
                {"type": "heading", "content": f"Category: {category}", "level": 2},
                {"type": "text", "content": f"**Status:** {enabled}"},
                {"type": "text", "content": f"**Mode:** {mode}"},
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
        if not fm.filters:
            return {
                "elements": [
                    {"type": "heading", "content": "Filter Configuration", "level": 2},
                    {"type": "text", "content": f"No filters loaded (would load from `{fm.filter_path}`)"},
                    {"type": "text", "content": "Use `filters('load')` to load filters from disk"},
                ]
            }

        # Build table data
        categories = fm.get_categories_summary()
        rows = []
        for cat in categories:
            mode = cat["mode"] or "exclude"
            mode_display = "include" if mode == "include" else "exclude"
            if cat["mode"] is None:
                mode_display = "exclude*"

            rows.append(
                {
                    "Category": cat["name"],
                    "Status": "enabled" if cat["enabled"] else "disabled",
                    "Mode": mode_display,
                    "Domains": str(cat["domain_count"]),
                    "Types": str(cat["type_count"]),
                }
            )

        elements = [
            {"type": "heading", "content": "Filter Configuration", "level": 2},
            {"type": "table", "headers": ["Category", "Status", "Mode", "Domains", "Types"], "rows": rows},
        ]

        if any(cat["mode"] is None for cat in categories):
            elements.append({"type": "text", "content": "_* Mode not specified, defaulting to exclude_"})

        return {"elements": elements}

    else:
        return error_response(f"Unknown action: {action}")
