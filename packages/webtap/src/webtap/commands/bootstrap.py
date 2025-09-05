"""Bootstrap command for downloading WebTap components."""

from webtap.app import app
from webtap.services.bootstrap import BootstrapService


@app.command(
    display="markdown",
    typer={"help": "Download WebTap components from GitHub"},
    fastmcp={"enabled": False},  # Not exposed to MCP
)
def bootstrap(state, what: str, force: bool = False) -> dict:
    """Download WebTap components from GitHub.

    Downloads filters or Chrome extension to their expected locations.
    After bootstrap, components are immediately available for use.

    Args:
        what: Component to bootstrap
            - "filters" - Download filters to ./.webtap/filters.json
            - "extension" - Download Chrome extension to ~/.config/webtap/extension/
        force: Overwrite existing files (default: False)

    Examples:
        # CLI usage
        webtap --cli bootstrap filters
        webtap --cli bootstrap filters --force
        webtap --cli bootstrap extension

        # REPL usage
        >>> bootstrap("filters")
        >>> bootstrap("extension", force=True)

        # After bootstrapping filters, load them
        >>> filters("load")
        ✓ Loaded 8 filter categories from .webtap/filters.json

    Returns:
        Markdown-formatted result with success/error messages
    """
    bs = BootstrapService()

    # Execute bootstrap
    if what == "filters":
        result = bs.bootstrap_filters(force=force)
    elif what == "extension":
        result = bs.bootstrap_extension(force=force)
    else:
        result = {
            "success": False,
            "message": f"Unknown component: {what}",
            "path": None,
            "details": "Valid components: 'filters', 'extension'",
        }

    # Format as markdown
    elements = []

    # Main message as alert
    level = "success" if result["success"] else "error"
    elements.append({"type": "alert", "content": result["message"], "level": level})

    # Add details if successful
    if result["success"]:
        if result.get("path"):
            elements.append({"type": "text", "content": f"**Location:** `{result['path']}`"})
        if result.get("details"):
            elements.append({"type": "text", "content": f"**Details:** {result['details']}"})

        # Add next steps for filters
        if what == "filters":
            elements.append({"type": "text", "content": "\n**Next steps:**"})
            elements.append(
                {
                    "type": "list",
                    "items": [
                        "Run `filters('load')` to load the filters",
                        "Run `filters()` to see loaded categories",
                        "Run `network()` to see filtered network requests",
                    ],
                }
            )

        # Add next steps for extension
        elif what == "extension":
            elements.append({"type": "text", "content": "\n**To install in Chrome:**"})
            elements.append(
                {
                    "type": "list",
                    "items": [
                        "Open chrome://extensions/",
                        "Enable Developer mode",
                        "Click 'Load unpacked'",
                        f"Select {result['path']}",
                    ],
                }
            )
    else:
        # Show error details
        if result.get("details"):
            elements.append({"type": "text", "content": f"**Info:** {result['details']}"})

    return {"elements": elements}
