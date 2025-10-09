"""Chrome extension setup service (cross-platform)."""

import json
import logging
from typing import Dict, Any

import requests

from .platform import get_platform_info, ensure_directories

logger = logging.getLogger(__name__)

# GitHub URLs for extension files
EXTENSION_BASE_URL = "https://raw.githubusercontent.com/angelsen/tap-tools/main/packages/webtap/extension"
EXTENSION_FILES = ["manifest.json", "content.js", "sidepanel.html", "sidepanel.js"]


class ExtensionSetupService:
    """Chrome extension installation service."""

    def __init__(self):
        self.info = get_platform_info()
        self.paths = self.info["paths"]

        # Extension goes in data directory (persistent app data)
        self.extension_dir = self.paths["data_dir"] / "extension"

    def install_extension(self, force: bool = False) -> Dict[str, Any]:
        """Install Chrome extension to platform-appropriate location.

        Args:
            force: Overwrite existing files

        Returns:
            Installation result
        """
        # Check if exists (manifest.json is required file)
        if (self.extension_dir / "manifest.json").exists() and not force:
            return {
                "success": False,
                "message": f"Extension already exists at {self.extension_dir}",
                "path": str(self.extension_dir),
                "details": "Use --force to overwrite",
            }

        # Ensure base directories exist
        ensure_directories()

        # If force, clean out old extension files first
        if force and self.extension_dir.exists():
            import shutil

            shutil.rmtree(self.extension_dir)
            logger.info(f"Cleaned old extension directory: {self.extension_dir}")

        # Create extension directory
        self.extension_dir.mkdir(parents=True, exist_ok=True)

        # Download each file
        downloaded = []
        failed = []

        for filename in EXTENSION_FILES:
            url = f"{EXTENSION_BASE_URL}/{filename}"
            target_file = self.extension_dir / filename

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
                "path": str(self.extension_dir),
                "details": f"Failed: {', '.join(failed)}",
            }

        logger.info(f"Extension installed to {self.extension_dir}")

        return {
            "success": True,
            "message": "Downloaded Chrome extension",
            "path": str(self.extension_dir),
            "details": f"Files: {', '.join(downloaded)}",
        }
