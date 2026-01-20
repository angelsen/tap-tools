"""Setup commands for WebTap components."""

from typing import Annotated

import typer

from webtap.app import app
from webtap.services.setup import SetupService, SUPPORTED_BROWSERS
from webtap.services.setup.platform import detect_browsers


@app.command(
    display="markdown",
    typer={"name": "setup-browser", "help": "Install browser wrapper and desktop launcher"},
    fastmcp={"enabled": False},
)
def setup_browser(
    state,
    browser: Annotated[str | None, typer.Option("--browser", "-b", help="Browser ID (chrome, edge)")] = None,
    force: bool = False,
    bindfs: bool = False,
) -> dict:
    """Install browser wrapper script and desktop launcher.

    Supported browsers:
    - chrome -> chrome-debug wrapper + Chrome Debug launcher
    - edge -> edge-debug wrapper + Edge Debug launcher

    Auto-detects installed browser if only one is found.
    Requires --browser flag if multiple browsers are installed.

    Args:
        browser: Browser ID (auto-detects if not specified)
        force: Overwrite existing files (default: False)
        bindfs: Use bindfs to mount real browser profile (Linux only, default: False)

    Returns:
        Markdown-formatted result with success/error messages
    """
    # Detect browsers if not specified
    if not browser:
        found = detect_browsers()
        if len(found) == 0:
            return _format_error(
                "No supported browser found",
                [
                    "Install Chrome: yay -S google-chrome",
                    "Install Edge: yay -S microsoft-edge-stable-bin",
                ],
            )
        elif len(found) > 1:
            return _format_error(
                "Multiple browsers found. Specify one with --browser",
                [f"webtap setup-browser --browser {b}" for b in found],
            )
        browser = found[0]

    # Validate browser
    if browser not in SUPPORTED_BROWSERS:
        return _format_error(
            f"Unsupported browser: {browser}",
            [f"Supported: {', '.join(SUPPORTED_BROWSERS.keys())}"],
        )

    service = SetupService()
    result = service.install_browser(browser, force=force, bindfs=bindfs)
    return _format_setup_result(result)


def _format_error(message: str, suggestions: list[str]) -> dict:
    """Format error response as markdown."""
    elements = [
        {"type": "alert", "message": message, "level": "error"},
        {"type": "heading", "level": 3, "content": "Suggestions"},
        {"type": "list", "items": suggestions},
    ]
    return {"elements": elements}


def _format_setup_result(result: dict) -> dict:
    """Format setup result as markdown."""
    elements = []

    # Main message as alert
    level = "success" if result["success"] else "error"
    elements.append({"type": "alert", "message": result["message"], "level": level})

    # Show paths if present
    if result.get("wrapper_path"):
        elements.append({"type": "text", "content": f"**Wrapper:** `{result['wrapper_path']}`"})
    if result.get("desktop_path"):
        elements.append({"type": "text", "content": f"**Desktop:** `{result['desktop_path']}`"})

    # Show details (PATH setup instructions, etc.)
    if result.get("details"):
        elements.append({"type": "text", "content": f"\n{result['details']}"})

    # Next steps on success
    if result["success"]:
        browser_config = result.get("browser", {})
        wrapper_name = browser_config.get("wrapper", "browser-debug")
        elements.append({"type": "heading", "level": 3, "content": "Usage"})
        elements.append(
            {
                "type": "list",
                "items": [
                    f"Run `{wrapper_name}` to start browser with debugging",
                    "Or use `webtap run-browser` for direct launch",
                    f"Desktop launcher available as '{browser_config.get('name', 'Browser')} Debug'",
                ],
            }
        )

    return {"elements": elements}


@app.command(
    display="markdown",
    typer={"name": "cleanup", "help": "Clean up old WebTap installations"},
    fastmcp={"enabled": False},
)
def cleanup(state, dry_run: bool = True) -> dict:
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
        elements.append({"type": "text", "content": "To perform cleanup: `cleanup --no-dry-run`"})
    else:
        elements.append({"type": "alert", "message": "Cleanup completed", "level": "success"})

    # Next steps
    elements.append({"type": "heading", "level": 3, "content": "Next Steps"})
    elements.append(
        {
            "type": "list",
            "items": [
                "Run `webtap install-extension` to install extension",
                "Run `webtap setup-browser` to install wrapper and desktop launcher",
                "Or `webtap setup-browser --bindfs` for bindfs mode",
            ],
        }
    )

    return {"elements": elements}
