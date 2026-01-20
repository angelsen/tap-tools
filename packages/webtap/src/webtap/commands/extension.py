"""Extension management commands.

PUBLIC API:
  - install_extension: Install Chrome extension to specified path
"""

import shutil
from importlib.resources import files
from pathlib import Path

from webtap.app import app
from webtap.services.setup.platform import get_platform_info

__all__ = ["install_extension"]


def _get_extension_source() -> Path:
    """Get path to bundled extension."""
    return Path(str(files("webtap").joinpath("extension")))


def _get_default_path() -> Path:
    """Get default extension install path."""
    return get_platform_info()["paths"]["data_dir"] / "extension"


@app.command(
    display="markdown",
    typer={"name": "install-extension", "help": "Install Chrome extension"},
    fastmcp={"enabled": False},
)
def install_extension(state, path: str | None = None) -> dict:
    """Install Chrome extension.

    Args:
        state: App state (unused)
        path: Destination directory (default: ~/.local/share/webtap/extension)

    Returns:
        Markdown-formatted installation result
    """
    source = _get_extension_source()
    dest = Path(path).expanduser().resolve() if path else _get_default_path()

    if not source.exists():
        return {
            "elements": [
                {"type": "alert", "message": "Bundled extension not found", "level": "error"},
                {"type": "text", "content": f"Expected at: `{source}`"},
            ]
        }

    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(source, dest)

    return {
        "elements": [
            {"type": "alert", "message": f"Extension installed to: {dest}", "level": "success"},
            {"type": "text", "content": "\n**To load in Chrome:**"},
            {
                "type": "list",
                "items": [
                    "Open chrome://extensions",
                    "Enable Developer mode",
                    "Click 'Load unpacked'",
                    f"Select: {dest}",
                ],
            },
        ]
    }
