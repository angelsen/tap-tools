"""Filter group management commands."""

from webtap.app import app
from webtap.commands._builders import info_response, error_response, table_response
from webtap.commands._tips import get_mcp_description

_filters_desc = get_mcp_description("filters")


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _filters_desc or ""}
)
def filters(
    state,
    add: str = None,  # type: ignore[reportArgumentType]
    remove: str = None,  # type: ignore[reportArgumentType]
    enable: str = None,  # type: ignore[reportArgumentType]
    disable: str = None,  # type: ignore[reportArgumentType]
    hide: dict = None,  # type: ignore[reportArgumentType]
) -> dict:
    """Manage filter groups for noise reduction.

    Args:
        add: Create new group with this name (requires hide=)
        remove: Delete group by name
        enable: Enable group by name
        disable: Disable group by name
        hide: Filter config for add {"types": [...], "urls": [...]}

    Examples:
        filters()                                           # Show all groups
        filters(add="assets", hide={"types": ["Image"]})   # Create group
        filters(enable="assets")                            # Enable group
        filters(disable="assets")                           # Disable group
        filters(remove="assets")                            # Delete group
    """
    # Handle add - create new group
    if add:
        if not hide:
            return error_response("hide= required when adding a group")

        try:
            state.client.filters_add(add, hide)
            return info_response(
                title="Group Created",
                fields={
                    "Name": add,
                    "Types": ", ".join(hide.get("types", [])) or "-",
                    "URLs": ", ".join(hide.get("urls", [])) or "-",
                },
            )
        except Exception as e:
            return error_response(str(e))

    # Handle remove - delete group
    if remove:
        try:
            result = state.client.filters_remove(remove)
            if result:
                return info_response(title="Group Removed", fields={"Name": remove})
            return error_response(f"Group '{remove}' not found")
        except Exception as e:
            return error_response(str(e))

    # Handle enable - toggle group on (in-memory)
    if enable:
        try:
            result = state.client.filters_enable(enable)
            if result:
                return info_response(title="Group Enabled", fields={"Name": enable})
            return error_response(f"Group '{enable}' not found")
        except Exception as e:
            return error_response(str(e))

    # Handle disable - toggle group off (in-memory)
    if disable:
        try:
            result = state.client.filters_disable(disable)
            if result:
                return info_response(title="Group Disabled", fields={"Name": disable})
            return error_response(f"Group '{disable}' not found")
        except Exception as e:
            return error_response(str(e))

    # Default: list all groups with status
    try:
        status = state.client.filters_status()
    except Exception as e:
        return error_response(str(e))

    if not status:
        return {
            "elements": [
                {"type": "heading", "content": "Filter Groups", "level": 2},
                {"type": "text", "content": "No filter groups configured."},
                {"type": "text", "content": 'Create one: `filters(add="assets", hide={"types": ["Image", "Font"]})`'},
            ]
        }

    # Build table
    rows = []
    for name, group in status.items():
        hide_cfg = group.get("hide", {})
        rows.append(
            {
                "Group": name,
                "Status": "enabled" if group.get("enabled") else "disabled",
                "Types": ", ".join(hide_cfg.get("types", [])) or "-",
                "URLs": ", ".join(hide_cfg.get("urls", [])) or "-",
            }
        )

    return table_response(
        title="Filter Groups",
        headers=["Group", "Status", "Types", "URLs"],
        rows=rows,
        tips=["Enabled groups hide matching requests from network()"],
    )


__all__ = ["filters"]
