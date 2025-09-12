"""Setup service for installing WebTap components (cross-platform).

PUBLIC API:
  - SetupService: Main service class for all setup operations
"""

from typing import Dict, Any

from .filters import FilterSetupService
from .extension import ExtensionSetupService
from .chrome import ChromeSetupService
from .desktop import DesktopSetupService
from .platform import get_platform_info, ensure_directories, APP_NAME

# Old installation paths to clean up
OLD_EXTENSION_PATH = ".config/webtap/extension"
OLD_WRAPPER_PATH = ".local/bin/wrappers/google-chrome-stable"
OLD_DESKTOP_PATH = ".local/share/applications/google-chrome.desktop"
OLD_DEBUG_DIR = ".config/google-chrome-debug"

# Path components
WRAPPERS_DIR = "wrappers"
GOOGLE_CHROME_STABLE = "google-chrome-stable"

# Size formatting constants
KB_SIZE = 1024
SIZE_FORMAT_KB = "{:.1f} KB"
SIZE_FORMAT_EMPTY = "empty"

# Mount point command
MOUNTPOINT_CMD = "mountpoint"
MOUNTPOINT_CHECK_FLAG = "-q"


class SetupService:
    """Orchestrator service for installing WebTap components.

    Delegates to specialized service classes for each component type.
    """

    def __init__(self):
        """Initialize setup service with platform information."""
        self.info = get_platform_info()
        ensure_directories()

        # Initialize component services
        self.filters_service = FilterSetupService()
        self.extension_service = ExtensionSetupService()
        self.chrome_service = ChromeSetupService()
        self.desktop_service = DesktopSetupService()

    def install_filters(self, force: bool = False) -> Dict[str, Any]:
        """Install filter configuration.

        Args:
            force: Overwrite existing file

        Returns:
            Dict with success, message, path, details
        """
        return self.filters_service.install_filters(force=force)

    def install_extension(self, force: bool = False) -> Dict[str, Any]:
        """Install Chrome extension files.

        Args:
            force: Overwrite existing files

        Returns:
            Dict with success, message, path, details
        """
        return self.extension_service.install_extension(force=force)

    def install_chrome_wrapper(self, force: bool = False, bindfs: bool = False) -> Dict[str, Any]:
        """Install Chrome wrapper script.

        Args:
            force: Overwrite existing script
            bindfs: Use bindfs to mount real Chrome profile (Linux only)

        Returns:
            Dict with success, message, path, details
        """
        return self.chrome_service.install_wrapper(force=force, bindfs=bindfs)

    def install_desktop_entry(self, force: bool = False) -> Dict[str, Any]:
        """Install desktop entry or app bundle for GUI integration.

        On Linux: Creates .desktop file
        On macOS: Creates .app bundle

        Args:
            force: Overwrite existing entry

        Returns:
            Dict with success, message, path, details
        """
        return self.desktop_service.install_launcher(force=force)

    def get_platform_info(self) -> Dict[str, Any]:
        """Get platform information for debugging.

        Returns:
            Platform information including paths and capabilities
        """
        return self.info

    def cleanup_old_installations(self, dry_run: bool = True) -> Dict[str, Any]:
        """Clean up old WebTap installations.

        Checks locations that webtap previously wrote to:
        - ~/.config/webtap/extension/ (old extension location)
        - ~/.local/bin/wrappers/google-chrome-stable (old wrapper location)
        - ~/.local/share/applications/google-chrome.desktop (old desktop entry)
        - ~/.config/google-chrome-debug (bindfs mount)

        Args:
            dry_run: If True, only report what would be done

        Returns:
            Dict with cleanup results
        """
        import shutil
        import subprocess
        from pathlib import Path

        result = {}

        # Check old extension location
        old_extension_path = Path.home() / OLD_EXTENSION_PATH
        if old_extension_path.exists():
            # Calculate size
            size = sum(f.stat().st_size for f in old_extension_path.rglob("*") if f.is_file())
            size_str = SIZE_FORMAT_KB.format(size / KB_SIZE) if size > 0 else SIZE_FORMAT_EMPTY

            result["old_extension"] = {"path": str(old_extension_path), "size": size_str, "removed": False}

            if not dry_run:
                try:
                    shutil.rmtree(old_extension_path)
                    result["old_extension"]["removed"] = True
                    # Also try to remove parent if empty
                    parent = old_extension_path.parent
                    if parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()
                except Exception as e:
                    result["old_extension"]["error"] = str(e)

        # Check old Chrome wrapper location
        old_wrapper_path = Path.home() / OLD_WRAPPER_PATH
        if old_wrapper_path.exists():
            result["old_wrapper"] = {"path": str(old_wrapper_path), "removed": False}

            if not dry_run:
                try:
                    old_wrapper_path.unlink()
                    result["old_wrapper"]["removed"] = True
                    # Try to remove wrappers dir if empty (but keep it if other wrappers exist)
                    wrappers_dir = old_wrapper_path.parent
                    if wrappers_dir.exists() and not any(wrappers_dir.iterdir()):
                        wrappers_dir.rmdir()
                except Exception as e:
                    result["old_wrapper"]["error"] = str(e)

        # Check old desktop entry
        old_desktop_path = Path.home() / OLD_DESKTOP_PATH
        if old_desktop_path.exists():
            # Check if it's our override (contains reference to wrapper)
            try:
                content = old_desktop_path.read_text()
                wrapper_ref = f"{WRAPPERS_DIR}/{GOOGLE_CHROME_STABLE}"
                if wrapper_ref in content or APP_NAME in content.lower():
                    result["old_desktop"] = {"path": str(old_desktop_path), "removed": False}

                    if not dry_run:
                        try:
                            old_desktop_path.unlink()
                            result["old_desktop"]["removed"] = True
                        except Exception as e:
                            result["old_desktop"]["error"] = str(e)
            except Exception:
                pass  # If we can't read it, skip it

        # Check for bindfs mount
        debug_dir = Path.home() / OLD_DEBUG_DIR
        if debug_dir.exists():
            try:
                # Check if it's a mount point
                output = subprocess.run([MOUNTPOINT_CMD, MOUNTPOINT_CHECK_FLAG, str(debug_dir)], capture_output=True)
                if output.returncode == 0:
                    result["bindfs_mount"] = str(debug_dir)
            except (FileNotFoundError, OSError):
                pass  # mountpoint command might not exist

        return result


__all__ = ["SetupService"]
