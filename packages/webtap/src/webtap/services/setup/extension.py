"""Chrome extension setup service (cross-platform).

PUBLIC API:
  - ExtensionSetupService: Chrome extension installation
  - ExtensionStatus: Status of extension installation
  - auto_update_extension: Auto-install or update extension if needed
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

import httpx

from .platform import get_platform_info, ensure_directories

logger = logging.getLogger(__name__)

_EXTENSION_BASE_URL = "https://raw.githubusercontent.com/angelsen/tap-tools/main/packages/webtap/extension"
_EXTENSION_FILES = [
    "manifest.json",
    "background.js",
    "sidepanel.html",
    "sidepanel.css",
    "main.js",
    "datatable.js",
    "bind.js",
    "client.js",
    "lib/ui.js",
]
_EXTENSION_CONTROLLERS = [
    "controllers/console.js",
    "controllers/filters.js",
    "controllers/header.js",
    "controllers/intercept.js",
    "controllers/network.js",
    "controllers/notices.js",
    "controllers/pages.js",
    "controllers/selections.js",
    "controllers/tabs.js",
    "controllers/targets.js",
    "controllers/theme.js",
]
_EXTENSION_ASSETS = [
    "assets/icon-16.png",
    "assets/icon-32.png",
    "assets/icon-48.png",
    "assets/icon-128.png",
]


@dataclass
class ExtensionStatus:
    """Status of extension installation."""

    status: str
    installed_hash: Optional[str]
    expected_hash: str
    manifest_changed: bool


def _is_editable_install() -> bool:
    """Check if webtap is installed in editable/dev mode.

    Uses importlib.metadata to check for direct_url.json (PEP 660).
    """
    try:
        import importlib.metadata

        dist = importlib.metadata.distribution("webtap")
        # Editable installs have origin pointing to local source
        origin = getattr(dist, "origin", None)
        return origin is not None
    except Exception:
        return False


def compute_extension_hash(extension_dir: Path) -> tuple[str, str]:
    """Compute hash of extension files.

    Args:
        extension_dir: Path to extension directory
    """
    all_hasher = hashlib.md5()
    manifest_hash = ""

    all_files = _EXTENSION_FILES + _EXTENSION_CONTROLLERS + _EXTENSION_ASSETS
    for filename in all_files:
        filepath = extension_dir / filename
        if filepath.exists():
            content = filepath.read_bytes()
            all_hasher.update(content)
            if filename == "manifest.json":
                manifest_hash = hashlib.md5(content).hexdigest()[:16]

    return all_hasher.hexdigest()[:16], manifest_hash


def get_expected_hash() -> tuple[str, str]:
    """Get expected hash from bundled extension source."""
    # Find the package source extension directory
    import webtap

    package_dir = Path(webtap.__file__).parent.parent.parent
    source_extension = package_dir / "extension"

    if source_extension.exists():
        return compute_extension_hash(source_extension)

    # Fallback: return empty hashes (will trigger update check)
    return "", ""


def check_extension_status() -> ExtensionStatus:
    """Check if extension needs install/update."""
    # Dev mode: editable install, skip auto-update
    if _is_editable_install():
        return ExtensionStatus(
            status="dev_mode",
            installed_hash=None,
            expected_hash="",
            manifest_changed=False,
        )

    info = get_platform_info()
    extension_dir = info["paths"]["data_dir"] / "extension"

    expected_full, expected_manifest = get_expected_hash()

    # Check if extension directory and manifest exist
    if not extension_dir.exists() or not (extension_dir / "manifest.json").exists():
        return ExtensionStatus(
            status="missing",
            installed_hash=None,
            expected_hash=expected_full,
            manifest_changed=False,
        )

    installed_full, installed_manifest = compute_extension_hash(extension_dir)

    # Check if hashes match
    if installed_full == expected_full:
        return ExtensionStatus(
            status="ok",
            installed_hash=installed_full,
            expected_hash=expected_full,
            manifest_changed=False,
        )

    # Check if manifest specifically changed
    manifest_changed = installed_manifest != expected_manifest

    return ExtensionStatus(
        status="manifest_changed" if manifest_changed else "outdated",
        installed_hash=installed_full,
        expected_hash=expected_full,
        manifest_changed=manifest_changed,
    )


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

        # Create extension directory and subdirectories
        self.extension_dir.mkdir(parents=True, exist_ok=True)
        (self.extension_dir / "lib").mkdir(exist_ok=True)
        (self.extension_dir / "controllers").mkdir(exist_ok=True)

        # Download text files (main files + controllers)
        downloaded = []
        failed = []

        for filename in _EXTENSION_FILES + _EXTENSION_CONTROLLERS:
            url = f"{_EXTENSION_BASE_URL}/{filename}"
            target_file = self.extension_dir / filename

            try:
                logger.info(f"Downloading {filename}")
                response = httpx.get(url, timeout=10)
                response.raise_for_status()

                # For manifest.json, validate it's proper JSON
                if filename == "manifest.json":
                    json.loads(response.text)

                target_file.write_text(response.text)
                downloaded.append(filename)

            except Exception as e:
                logger.error(f"Failed to download {filename}: {e}")
                failed.append(filename)

        # Download binary assets (icons)
        assets_dir = self.extension_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        for asset_path in _EXTENSION_ASSETS:
            url = f"{_EXTENSION_BASE_URL}/{asset_path}"
            target_file = self.extension_dir / asset_path

            try:
                logger.info(f"Downloading {asset_path}")
                response = httpx.get(url, timeout=10)
                response.raise_for_status()

                target_file.write_bytes(response.content)
                downloaded.append(asset_path)

            except Exception as e:
                logger.error(f"Failed to download {asset_path}: {e}")
                failed.append(asset_path)

        # Determine success level
        if not downloaded:
            return {
                "success": False,
                "message": "Failed to download any extension files",
                "path": None,
                "details": "Check network connection and try again",
            }

        total_files = len(_EXTENSION_FILES) + len(_EXTENSION_CONTROLLERS) + len(_EXTENSION_ASSETS)
        if failed:
            # Partial success - some files downloaded
            return {
                "success": True,  # Partial is still success
                "message": f"Downloaded {len(downloaded)}/{total_files} files",
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


def auto_update_extension() -> ExtensionStatus:
    """Auto-install or update extension if needed."""
    status = check_extension_status()

    # Dev mode or already OK - nothing to do
    if status.status in ("ok", "dev_mode"):
        return status

    # Remember what operation we're performing
    operation = status.status

    # Install or update extension
    service = ExtensionSetupService()
    result = service.install_extension(force=True)

    if not result["success"]:
        raise Exception(f"Failed to install extension: {result['message']}")

    # Return status indicating what operation was performed
    # (not the re-checked status which would always be "ok")
    return ExtensionStatus(
        status=operation,  # Preserve original status to indicate what was done
        installed_hash=status.expected_hash,  # Now matches expected
        expected_hash=status.expected_hash,
        manifest_changed=status.manifest_changed,
    )


__all__ = ["ExtensionSetupService", "ExtensionStatus", "auto_update_extension"]
