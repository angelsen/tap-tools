"""Chrome extension setup functionality for WebTap."""

import json
import logging
from pathlib import Path
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)

# GitHub URLs for extension files
EXTENSION_BASE_URL = "https://raw.githubusercontent.com/angelsen/tap-tools/main/packages/webtap/extension"
EXTENSION_FILES = ["manifest.json", "popup.html", "popup.js"]


def install_extension(force: bool = False) -> Dict[str, Any]:
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

    for filename in EXTENSION_FILES:
        url = f"{EXTENSION_BASE_URL}/{filename}"
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
            "message": f"Downloaded {len(downloaded)}/{len(EXTENSION_FILES)} files",
            "path": str(target_dir),
            "details": f"Failed: {', '.join(failed)}",
        }

    return {
        "success": True,
        "message": "Downloaded Chrome extension",
        "path": str(target_dir),
        "details": f"Files: {', '.join(downloaded)}",
    }
