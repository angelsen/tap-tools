"""Setup service for installing WebTap components."""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)


class SetupService:
    """Service for installing WebTap components."""

    # GitHub URLs
    FILTERS_URL = "https://raw.githubusercontent.com/angelsen/tap-tools/main/packages/webtap/data/filters.json"
    EXTENSION_BASE_URL = "https://raw.githubusercontent.com/angelsen/tap-tools/main/packages/webtap/extension"
    EXTENSION_FILES = ["manifest.json", "popup.html", "popup.js"]

    def install_filters(self, force: bool = False) -> Dict[str, Any]:
        """Install filters to .webtap/filters.json.

        Args:
            force: Overwrite existing file

        Returns:
            Dict with success, message, path, details
        """
        # Same path that FilterManager uses
        target_path = Path.cwd() / ".webtap" / "filters.json"

        # Check if exists
        if target_path.exists() and not force:
            return {
                "success": False,
                "message": f"Filters already exist at {target_path}",
                "path": str(target_path),
                "details": "Use --force to overwrite",
            }

        # Download from GitHub
        try:
            logger.info(f"Downloading filters from {self.FILTERS_URL}")
            response = requests.get(self.FILTERS_URL, timeout=10)
            response.raise_for_status()

            # Validate it's proper JSON
            filters_data = json.loads(response.text)

            # Quick validation - should have dict structure
            if not isinstance(filters_data, dict):
                return {
                    "success": False,
                    "message": "Invalid filter format - expected JSON object",
                    "path": None,
                    "details": None,
                }

            # Count categories for user feedback
            category_count = len(filters_data)

            # Create directory and save
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(response.text)

            logger.info(f"Saved {category_count} filter categories to {target_path}")

            return {
                "success": True,
                "message": f"Downloaded {category_count} filter categories",
                "path": str(target_path),
                "details": f"Categories: {', '.join(filters_data.keys())}",
            }

        except requests.RequestException as e:
            logger.error(f"Network error downloading filters: {e}")
            return {"success": False, "message": f"Network error: {e}", "path": None, "details": None}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in filters: {e}")
            return {"success": False, "message": f"Invalid JSON format: {e}", "path": None, "details": None}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"success": False, "message": f"Failed to download filters: {e}", "path": None, "details": None}

    def install_extension(self, force: bool = False) -> Dict[str, Any]:
        """Install Chrome extension to ~/.config/webtap/extension/.

        Args:
            force: Overwrite existing files

        Returns:
            Dict with success, message, path, details
        """
        # XDG config directory for Linux
        target_dir = Path.home() / ".config" / "webtap" / "extension"

        # Check if exists (manifest.json is required file)
        if (target_dir / "manifest.json").exists() and not force:
            return {
                "success": False,
                "message": f"Extension already exists at {target_dir}",
                "path": str(target_dir),
                "details": "Use --force to overwrite",
            }

        # Create directory
        target_dir.mkdir(parents=True, exist_ok=True)

        # Download each file
        downloaded = []
        failed = []

        for filename in self.EXTENSION_FILES:
            url = f"{self.EXTENSION_BASE_URL}/{filename}"
            target_file = target_dir / filename

            try:
                logger.info(f"Downloading {filename}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                # For manifest.json, validate it's proper JSON
                if filename == "manifest.json":
                    json.loads(response.text)

                target_file.write_text(response.text)
                downloaded.append(filename)

            except Exception as e:
                logger.error(f"Failed to download {filename}: {e}")
                failed.append(filename)

        # Determine success level
        if not downloaded:
            return {
                "success": False,
                "message": "Failed to download any extension files",
                "path": None,
                "details": "Check network connection and try again",
            }

        if failed:
            # Partial success - some files downloaded
            return {
                "success": True,  # Partial is still success
                "message": f"Downloaded {len(downloaded)}/{len(self.EXTENSION_FILES)} files",
                "path": str(target_dir),
                "details": f"Failed: {', '.join(failed)}",
            }

        return {
            "success": True,
            "message": "Downloaded Chrome extension",
            "path": str(target_dir),
            "details": f"Files: {', '.join(downloaded)}",
        }

    def install_chrome_wrapper(self, force: bool = False) -> Dict[str, Any]:
        """Install Chrome wrapper script for debugging.

        Args:
            force: Overwrite existing script

        Returns:
            Dict with success, message, path, details
        """
        target_path = Path.home() / ".local" / "bin" / "wrappers" / "google-chrome-stable"

        if target_path.exists() and not force:
            return {
                "success": False,
                "message": "Chrome wrapper already exists",
                "path": str(target_path),
                "details": "Use --force to overwrite",
            }

        wrapper_script = """#!/bin/bash
# Chrome wrapper using bindfs for perfect state sync with debug port

DEBUG_DIR="$HOME/.config/google-chrome-debug"
REAL_DIR="$HOME/.config/google-chrome"

# Check if bindfs is installed
if ! command -v bindfs &>/dev/null; then
    echo "Error: bindfs not installed. Install with: yay -S bindfs" >&2
    exit 1
fi

# Mount real profile via bindfs if not already mounted
if ! mountpoint -q "$DEBUG_DIR" 2>/dev/null; then
    mkdir -p "$DEBUG_DIR"
    if ! bindfs --no-allow-other "$REAL_DIR" "$DEBUG_DIR"; then
        echo "Error: Failed to mount Chrome profile via bindfs" >&2
        exit 1
    fi
    echo "Chrome debug profile mounted. To unmount: fusermount -u $DEBUG_DIR" >&2
fi

# Launch Chrome with debugging on bindfs mount
exec /usr/bin/google-chrome-stable \\
    --remote-debugging-port=9222 \\
    --remote-allow-origins='*' \\
    --user-data-dir="$DEBUG_DIR" \\
    "$@"
"""

        # Create directory and save
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(wrapper_script)
        target_path.chmod(0o755)  # Make executable

        # Check PATH
        path_dirs = os.environ.get("PATH", "").split(":")
        wrapper_dir = str(target_path.parent)
        in_path = wrapper_dir in path_dirs

        logger.info(f"Installed Chrome wrapper to {target_path}")

        return {
            "success": True,
            "message": "Installed Chrome wrapper script",
            "path": str(target_path),
            "details": "Already in PATH ✓" if in_path else "Add to PATH",
        }


__all__ = ["SetupService"]
