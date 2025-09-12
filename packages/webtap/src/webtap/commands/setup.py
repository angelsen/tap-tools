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
    """Download Chrome extension to platform-appropriate location.

    Linux: ~/.local/share/webtap/extension/
    macOS: ~/Library/Application Support/webtap/extension/

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
def setup_chrome(state, force: bool = False, bindfs: bool = False) -> dict:
    """Install Chrome wrapper script 'chrome-debug' to ~/.local/bin/.

    The wrapper enables remote debugging on port 9222.
    Same location on both Linux and macOS: ~/.local/bin/chrome-debug

    Args:
        force: Overwrite existing script (default: False)
        bindfs: Use bindfs to mount real Chrome profile for debugging (Linux only, default: False)

    Returns:
        Markdown-formatted result with success/error messages
    """
    service = SetupService()
    result = service.install_chrome_wrapper(force=force, bindfs=bindfs)
    return _format_setup_result(result, "chrome")


@app.command(
    display="markdown",
    typer={"name": "setup-desktop", "help": "Install Chrome Debug GUI launcher"},
    fastmcp={"enabled": False},
)
def setup_desktop(state, force: bool = False) -> dict:
    """Install Chrome Debug GUI launcher (separate from system Chrome).

    Linux: Creates desktop entry at ~/.local/share/applications/chrome-debug.desktop
           Shows as "Chrome Debug" in application menu.

    macOS: Creates app bundle at ~/Applications/Chrome Debug.app
           Shows as "Chrome Debug" in Launchpad and Spotlight.

    Args:
        force: Overwrite existing launcher (default: False)

    Returns:
        Markdown-formatted result with success/error messages
    """
    service = SetupService()
    result = service.install_desktop_entry(force=force)
    return _format_setup_result(result, "desktop")


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
                            "Run `chrome-debug` to start Chrome with debugging",
                            "Or use `run-chrome` command for direct launch",
                        ],
                    }
                )
        elif component == "desktop":
            # Platform-specific instructions are already in the service's details
            pass

    return {"elements": elements}


@app.command(
    display="markdown",
    typer={"name": "setup-cleanup", "help": "Clean up old WebTap installations"},
    fastmcp={"enabled": False},
)
def setup_cleanup(state, dry_run: bool = True) -> dict:
    """Clean up old WebTap installations from previous versions.

    Checks for and removes:
    - Old extension location (~/.config/webtap/extension/)
    - Old desktop entries created by webtap
    - Unmounted bindfs directories

    Args:
        dry_run: Only show what would be cleaned (default: True)

    Returns:
        Markdown report of cleanup actions
    """
    service = SetupService()
    result = service.cleanup_old_installations(dry_run=dry_run)

    elements = []

    # Header
    elements.append({"type": "heading", "level": 2, "content": "WebTap Cleanup Report"})

    # Old installations found
    if result.get("old_extension"):
        elements.append({"type": "heading", "level": 3, "content": "Old Extension Location"})
        elements.append({"type": "text", "content": f"Found: `{result['old_extension']['path']}`"})
        elements.append({"type": "text", "content": f"Size: {result['old_extension']['size']}"})
        if not dry_run and result["old_extension"].get("removed"):
            elements.append({"type": "alert", "message": "✓ Removed old extension", "level": "success"})
        elif dry_run:
            elements.append({"type": "alert", "message": "Would remove (dry-run mode)", "level": "info"})

    # Old Chrome wrapper
    if result.get("old_wrapper"):
        elements.append({"type": "heading", "level": 3, "content": "Old Chrome Wrapper"})
        elements.append({"type": "text", "content": f"Found: `{result['old_wrapper']['path']}`"})
        if not dry_run and result["old_wrapper"].get("removed"):
            elements.append({"type": "alert", "message": "✓ Removed old wrapper", "level": "success"})
        elif dry_run:
            elements.append({"type": "alert", "message": "Would remove (dry-run mode)", "level": "info"})

    # Old desktop entry
    if result.get("old_desktop"):
        elements.append({"type": "heading", "level": 3, "content": "Old Desktop Entry"})
        elements.append({"type": "text", "content": f"Found: `{result['old_desktop']['path']}`"})
        if not dry_run and result["old_desktop"].get("removed"):
            elements.append({"type": "alert", "message": "✓ Removed old desktop entry", "level": "success"})
        elif dry_run:
            elements.append({"type": "alert", "message": "Would remove (dry-run mode)", "level": "info"})

    # Check for bindfs mounts
    if result.get("bindfs_mount"):
        elements.append({"type": "heading", "level": 3, "content": "Bindfs Mount Detected"})
        elements.append({"type": "text", "content": f"Mount: `{result['bindfs_mount']}`"})
        elements.append(
            {"type": "alert", "message": "To unmount: fusermount -u " + result["bindfs_mount"], "level": "warning"}
        )

    # Summary
    elements.append({"type": "heading", "level": 3, "content": "Summary"})
    if dry_run:
        elements.append({"type": "text", "content": "**Dry-run mode** - no changes made"})
        elements.append({"type": "text", "content": "To perform cleanup: `setup-cleanup --no-dry-run`"})
    else:
        elements.append({"type": "alert", "message": "Cleanup completed", "level": "success"})

    # Next steps
    elements.append({"type": "heading", "level": 3, "content": "Next Steps"})
    elements.append(
        {
            "type": "list",
            "items": [
                "Run `setup-extension` to install extension in new location",
                "Run `setup-chrome --bindfs` for bindfs mode or `setup-chrome` for standard mode",
                "Run `setup-desktop` to create Chrome Debug launcher",
            ],
        }
    )

    return {"elements": elements}
