"""Desktop entry setup functionality for WebTap."""

import re
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def install_desktop_entry(force: bool = False) -> Dict[str, Any]:
    """Install desktop entry to override system Chrome launcher.

    Creates a .desktop file that makes Chrome launch with our debug wrapper
    when started from GUI (app launcher, dock, etc).

    Args:
        force: Overwrite existing desktop entry

    Returns:
        Dict with success, message, path, details
    """
    # Check if wrapper exists first
    wrapper_path = Path.home() / ".local" / "bin" / "wrappers" / "google-chrome-stable"
    if not wrapper_path.exists():
        return {
            "success": False,
            "message": "Chrome wrapper not found. Run 'setup-chrome' first",
            "path": None,
            "details": f"Expected wrapper at {wrapper_path}",
        }

    # Desktop entry location (user override of system entry)
    desktop_path = Path.home() / ".local" / "share" / "applications" / "google-chrome.desktop"

    if desktop_path.exists() and not force:
        return {
            "success": False,
            "message": "Desktop entry already exists",
            "path": str(desktop_path),
            "details": "Use --force to overwrite",
        }

    # Get system Chrome desktop file for reference
    system_desktop = _find_system_desktop_file()

    if system_desktop:
        desktop_content = _create_from_system_desktop(system_desktop, wrapper_path)
        source_info = system_desktop.name
    else:
        desktop_content = _create_minimal_desktop(wrapper_path)
        source_info = "minimal template"

    # Create directory and save
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    desktop_path.write_text(desktop_content)
    desktop_path.chmod(0o644)  # Standard permissions for desktop files

    logger.info(f"Installed desktop entry to {desktop_path}")

    return {
        "success": True,
        "message": "Installed Chrome desktop entry with debug wrapper",
        "path": str(desktop_path),
        "details": f"Based on {source_info}",
    }


def _find_system_desktop_file() -> Path | None:
    """Find the system Chrome desktop file."""
    for system_path in [
        Path("/usr/share/applications/google-chrome.desktop"),
        Path("/usr/share/applications/google-chrome-stable.desktop"),
        Path("/usr/local/share/applications/google-chrome.desktop"),
    ]:
        if system_path.exists():
            return system_path
    return None


def _create_from_system_desktop(system_desktop: Path, wrapper_path: Path) -> str:
    """Create desktop content by modifying the system desktop file."""
    try:
        system_content = system_desktop.read_text()

        # Replace all Exec= lines to use our wrapper
        # Match Exec= lines that point to chrome executables
        exec_pattern = re.compile(
            r"^Exec=.*?(?:google-chrome-stable|google-chrome|chromium|chrome)(?:\s|$)", re.MULTILINE
        )

        # Replace with our wrapper, preserving arguments
        def replace_exec(match):
            line = match.group(0)
            # Find where the executable ends and arguments begin
            # Look for common chrome executables
            for exe in ["google-chrome-stable", "google-chrome", "chromium-browser", "chromium", "chrome"]:
                if exe in line:
                    # Split at the executable name
                    parts = line.split(exe, 1)
                    if len(parts) > 1:
                        # Has arguments after executable
                        return f"Exec={wrapper_path}{parts[1]}"
                    else:
                        # No arguments
                        return f"Exec={wrapper_path}"
            # Fallback - shouldn't happen
            return f"Exec={wrapper_path}"

        desktop_content = exec_pattern.sub(replace_exec, system_content)

        # Also handle TryExec if present (used to check if program exists)
        tryexec_pattern = re.compile(
            r"^TryExec=.*?(?:google-chrome-stable|google-chrome|chromium|chrome)", re.MULTILINE
        )
        desktop_content = tryexec_pattern.sub(f"TryExec={wrapper_path}", desktop_content)

        return desktop_content

    except Exception as e:
        logger.warning(f"Failed to parse system desktop file, using minimal entry: {e}")
        return _create_minimal_desktop(wrapper_path)


def _create_minimal_desktop(wrapper_path: Path) -> str:
    """Create a minimal desktop entry from scratch."""
    return f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Google Chrome
GenericName=Web Browser
Comment=Access the Internet
Icon=google-chrome
Categories=Network;WebBrowser;
MimeType=application/pdf;application/rdf+xml;application/rss+xml;application/xhtml+xml;application/xhtml_xml;application/xml;image/gif;image/jpeg;image/png;image/webp;text/html;text/xml;x-scheme-handler/ftp;x-scheme-handler/http;x-scheme-handler/https;
StartupWMClass=Google-chrome
StartupNotify=true
Terminal=false
Exec={wrapper_path} %U
Actions=new-window;new-private-window;

[Desktop Action new-window]
Name=New Window
StartupWMClass=Google-chrome
Exec={wrapper_path}

[Desktop Action new-private-window]
Name=New Incognito Window
StartupWMClass=Google-chrome
Exec={wrapper_path} --incognito
"""
