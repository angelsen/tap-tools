"""Setup commands for WebTap components."""

from webtap.app import app
from webtap.services.setup import SetupService


@app.command(
    display="markdown",
    typer={"name": "setup-filters", "help": "Download filter configuration from GitHub"},
    fastmcp={"enabled": False},
)
def setup_filters(state, force: bool = False) -> dict:
    """Download filter configuration to ./.webtap/filters.json.

    Args:
        force: Overwrite existing file (default: False)

    Returns:
        Markdown-formatted result with success/error messages
    """
    service = SetupService()
    result = service.install_filters(force=force)
    return _format_setup_result(result, "filters")


@app.command(
    display="markdown",
    typer={"name": "setup-extension", "help": "Download Chrome extension from GitHub"},
    fastmcp={"enabled": False},
)
def setup_extension(state, force: bool = False) -> dict:
    """Download Chrome extension to ~/.config/webtap/extension/.

    Args:
        force: Overwrite existing files (default: False)

    Returns:
        Markdown-formatted result with success/error messages
    """
    service = SetupService()
    result = service.install_extension(force=force)
    return _format_setup_result(result, "extension")


@app.command(
    display="markdown",
    typer={"name": "setup-chrome", "help": "Install Chrome wrapper script for debugging"},
    fastmcp={"enabled": False},
)
def setup_chrome(state, force: bool = False) -> dict:
    """Install Chrome wrapper to ~/.local/bin/wrappers/google-chrome-stable.

    Args:
        force: Overwrite existing script (default: False)

    Returns:
        Markdown-formatted result with success/error messages
    """
    service = SetupService()
    result = service.install_chrome_wrapper(force=force)
    return _format_setup_result(result, "chrome")


def _format_setup_result(result: dict, component: str) -> dict:
    """Format setup result as markdown."""
    elements = []

    # Main message as alert (using "message" key for consistency)
    level = "success" if result["success"] else "error"
    elements.append({"type": "alert", "message": result["message"], "level": level})

    # Add details if present
    if result.get("path"):
        elements.append({"type": "text", "content": f"**Location:** `{result['path']}`"})
    if result.get("details"):
        elements.append({"type": "text", "content": f"**Details:** {result['details']}"})

    # Component-specific next steps
    if result["success"]:
        if component == "filters":
            elements.append({"type": "text", "content": "\n**Next steps:**"})
            elements.append(
                {
                    "type": "list",
                    "items": [
                        "Run `filters('load')` to load the filters",
                        "Run `filters()` to see loaded categories",
                    ],
                }
            )
        elif component == "extension":
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
        elif component == "chrome":
            if "Add to PATH" in result.get("details", ""):
                elements.append({"type": "text", "content": "\n**Setup PATH:**"})
                elements.append(
                    {
                        "type": "code_block",
                        "language": "bash",
                        "content": 'export PATH="$HOME/.local/bin/wrappers:$PATH"',
                    }
                )
                elements.append({"type": "text", "content": "Add to ~/.bashrc to make permanent"})
            else:
                elements.append({"type": "text", "content": "\n**Usage:**"})
                elements.append(
                    {
                        "type": "list",
                        "items": [
                            "Run `google-chrome-stable` to start Chrome with debugging",
                            "Or use `run-chrome` command for direct launch",
                        ],
                    }
                )

    return {"elements": elements}
