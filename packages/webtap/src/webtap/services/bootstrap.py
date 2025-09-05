"""Bootstrap service for downloading WebTap components.

This service downloads filters and Chrome extension files from GitHub
to their expected locations for use by other WebTap services.
"""

from pathlib import Path
import requests
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BootstrapService:
    """Bootstrap service for downloading WebTap components.

    This service is independent and doesn't interact with other services.
    It simply downloads files to the correct locations where other services
    expect them to be.
    """

    # Fixed GitHub URLs
    FILTERS_URL = "https://raw.githubusercontent.com/angelsen/tap-tools/main/packages/webtap/data/filters.json"
    EXTENSION_BASE_URL = "https://raw.githubusercontent.com/angelsen/tap-tools/main/packages/webtap/extension"
    EXTENSION_FILES = ["manifest.json", "popup.html", "popup.js"]

    def __init__(self):
        """Initialize bootstrap service."""
        # No state needed - stateless service
        pass

    def bootstrap_filters(self, force: bool = False) -> Dict[str, Any]:
        """Download filters to .webtap/filters.json where FilterManager expects them.

        The FilterManager.load() method looks for filters at:
        Path.cwd() / ".webtap" / "filters.json"

        So we save there, and FilterManager.load() will find them automatically.

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
                "details": "Use force=True or --force to overwrite",
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

    def bootstrap_extension(self, force: bool = False) -> Dict[str, Any]:
        """Download extension to ~/.config/webtap/extension/.

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
                "details": "Use force=True or --force to overwrite",
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


__all__ = ["BootstrapService"]
