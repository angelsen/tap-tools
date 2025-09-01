"""Network request filtering and categorization management commands.

PUBLIC API:
  - filters: Manage network request filters with pattern matching and persistence
"""

from typing import Dict, Any

from webtap.app import app
from webtap.commands._utils import build_info_response
from webtap.commands._errors import error_response
from webtap.commands._symbols import sym
from replkit2.textkit import markdown


@app.command(display="markdown")
def filters(
    state,
    add: Dict[str, str] | None = None,
    remove: Dict[str, str] | None = None,
    update: Dict[str, Any] | None = None,
    delete: str | None = None,
    list: str | None = None,
    save: bool = False,
    load: bool = False,
) -> dict:
    """
    Manage network request filters.

    Filters are managed by the service and can be persisted to .webtap/filters.json.

    Args:
        add: Add pattern {"domain": "*pattern*", "category": "ads"}
             or {"type": "Ping", "category": "tracking"}
        remove: Remove pattern {"domain": "*pattern*"} or {"type": "Ping"}
        update: Update category {"category": "ads", "domains": [...], "types": [...]}
        delete: Delete category name
        list: List specific category name
        save: Save current filters to .webtap/filters.json
        load: Load filters from .webtap/filters.json

    Examples:
        filters()                                              # Show all filters
        filters(list="ads")                                   # List ads filters
        filters(add={"domain": "*doubleclick*", "category": "ads"})
        filters(add={"type": "Ping", "category": "tracking"})
        filters(remove={"domain": "*doubleclick*"})
        filters(update={"category": "ads", "domains": ["*google*", "*facebook*"]})
        filters(delete="ads")
        filters(save=True)                                    # Persist to disk
        filters(load=True)                                    # Load from disk

    Returns:
        Current filter configuration or operation result
    """
    fm = state.service.filters

    # Handle load operation
    if load:
        if fm.load():
            # Convert display info to markdown
            display_info = fm.get_display_info()
            builder = markdown().heading("Filters Loaded", level=2)
            builder.code_block(display_info, language="")
            return builder.build()
        else:
            return error_response("no_data", custom_message=f"No filters found at {fm.filter_path}")

    # Handle save operation
    if save:
        if fm.save():
            return build_info_response(
                title="Filters Saved", fields={"Categories": f"{len(fm.filters)}", "Path": str(fm.filter_path)}
            )
        else:
            return error_response("custom", custom_message="Failed to save filters")

    # Handle add operation
    if add:
        category = add.get("category", "custom")

        if "domain" in add:
            if fm.add_pattern(add["domain"], category, "domain"):
                return build_info_response(
                    title="Filter Added",
                    fields={"Type": "Domain pattern", "Pattern": add["domain"], "Category": category},
                )
            return error_response(
                "custom", custom_message=f"Domain pattern '{add['domain']}' already in category '{category}'"
            )

        if "type" in add:
            if fm.add_pattern(add["type"], category, "type"):
                return build_info_response(
                    title="Filter Added", fields={"Type": "Resource type", "Pattern": add["type"], "Category": category}
                )
            return error_response("custom", custom_message=f"Type '{add['type']}' already in category '{category}'")

    # Handle remove operation
    elif remove:
        if "domain" in remove:
            category = fm.remove_pattern(remove["domain"], "domain")
            if category:
                return build_info_response(
                    title="Filter Removed",
                    fields={"Type": "Domain pattern", "Pattern": remove["domain"], "Category": category},
                )

        if "type" in remove:
            category = fm.remove_pattern(remove["type"], "type")
            if category:
                return build_info_response(
                    title="Filter Removed",
                    fields={"Type": "Resource type", "Pattern": remove["type"], "Category": category},
                )

        return error_response("custom", custom_message=f"Pattern not found: {remove}")

    # Handle update operation
    elif update:
        category = update.get("category")
        if not category:
            return error_response("custom", custom_message="'category' required for update")

        fm.update_category(category, domains=update.get("domains"), types=update.get("types"))
        return build_info_response(title="Category Updated", fields={"Category": category})

    # Handle delete operation
    elif delete:
        if fm.delete_category(delete):
            return build_info_response(title="Category Deleted", fields={"Category": delete})
        return error_response("custom", custom_message=f"Category '{delete}' not found")

    # Handle list operation
    elif list:
        if list in fm.filters:
            filters = fm.filters[list]
            enabled = sym("connected") if list in fm.enabled_categories else sym("disconnected")

            builder = markdown().heading(f"Category: {list}", level=2)
            builder.text(f"**Status:** {enabled}")

            if filters.get("domains"):
                builder.text("**Domain Patterns:**")
                builder.list(filters["domains"])

            if filters.get("types"):
                builder.text("**Resource Types:**")
                builder.list(filters["types"])

            return builder.build()
        return error_response("custom", custom_message=f"Category '{list}' not found")

    # Default: show all filters
    display_info = fm.get_display_info()
    builder = markdown().heading("Filter Configuration", level=2)
    builder.code_block(display_info, language="")
    return builder.build()
