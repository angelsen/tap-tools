"""Setup service for installing WebTap components (cross-platform).

PUBLIC API:
  - SetupService: Orchestrator for WebTap component installation
"""

from typing import Any

from .browser import BrowserSetupService
from .desktop import DesktopSetupService
from .platform import (
    get_platform_info,
    ensure_directories,
    get_browser_info,
    SUPPORTED_BROWSERS,
    APP_NAME,
)

_OLD_EXTENSION_PATH = ".config/webtap/extension"
_OLD_WRAPPER_PATH = ".local/bin/wrappers/google-chrome-stable"
_OLD_DESKTOP_PATH = ".local/share/applications/google-chrome.desktop"
_OLD_DEBUG_DIR = ".config/google-chrome-debug"

_WRAPPERS_DIR = "wrappers"
_GOOGLE_CHROME_STABLE = "google-chrome-stable"

_KB_SIZE = 1024
_SIZE_FORMAT_KB = "{:.1f} KB"
_SIZE_FORMAT_EMPTY = "empty"

_MOUNTPOINT_CMD = "mountpoint"
_MOUNTPOINT_CHECK_FLAG = "-q"


class SetupService:
    """Orchestrator service for installing WebTap components.

    Delegates to specialized service classes for each component type.
    """

    def __init__(self):
        """Initialize setup service with platform information."""
        self.info = get_platform_info()
        ensure_directories()

        # Initialize component services
        self.browser_service = BrowserSetupService()
        self.desktop_service = DesktopSetupService()

    def install_browser(self, browser_id: str, force: bool = False, bindfs: bool = False) -> dict[str, Any]:
        """Install browser wrapper and desktop launcher.

        Args:
            browser_id: Browser ID (e.g., 'chrome', 'edge')
            force: Overwrite existing files
            bindfs: Use bindfs to mount real browser profile (Linux only)

        Returns:
            Dict with success, message, path, details, wrapper_result, desktop_result
        """
        # Get browser config
        browser_config = get_browser_info(browser_id)
        if not browser_config:
            return {
                "success": False,
                "message": f"Unsupported browser: {browser_id}",
                "details": f"Supported: {', '.join(SUPPORTED_BROWSERS.keys())}",
            }

        # Install wrapper first
        wrapper_result = self.browser_service.install(browser_id, force=force, bindfs=bindfs)
        if not wrapper_result["success"]:
            return wrapper_result

        # Install desktop entry
        desktop_result = self.desktop_service.install_launcher(browser_id, browser_config, force=force)

        # Combine results
        if desktop_result["success"]:
            return {
                "success": True,
                "message": f"{browser_config['name']} Debug setup complete",
                "wrapper_path": wrapper_result.get("path"),
                "desktop_path": desktop_result.get("path"),
                "details": wrapper_result.get("details", ""),
                "browser": browser_config,
                "wrapper_result": wrapper_result,
                "desktop_result": desktop_result,
            }
        else:
            # Wrapper installed but desktop failed
            return {
                "success": True,  # Partial success
                "message": f"Wrapper installed, desktop entry failed: {desktop_result['message']}",
                "wrapper_path": wrapper_result.get("path"),
                "details": wrapper_result.get("details", ""),
                "browser": browser_config,
                "wrapper_result": wrapper_result,
                "desktop_result": desktop_result,
            }

    def get_platform_info(self) -> dict[str, Any]:
        """Get platform information for debugging.

        Returns:
            Platform information including paths and capabilities
        """
        return self.info

    def cleanup_old_installations(self, dry_run: bool = True) -> dict[str, Any]:
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
        old_extension_path = Path.home() / _OLD_EXTENSION_PATH
        if old_extension_path.exists():
            # Calculate size
            size = sum(f.stat().st_size for f in old_extension_path.rglob("*") if f.is_file())
            size_str = _SIZE_FORMAT_KB.format(size / _KB_SIZE) if size > 0 else _SIZE_FORMAT_EMPTY

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
        old_wrapper_path = Path.home() / _OLD_WRAPPER_PATH
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
        old_desktop_path = Path.home() / _OLD_DESKTOP_PATH
        if old_desktop_path.exists():
            # Check if it's our override (contains reference to wrapper)
            try:
                content = old_desktop_path.read_text()
                wrapper_ref = f"{_WRAPPERS_DIR}/{_GOOGLE_CHROME_STABLE}"
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
        debug_dir = Path.home() / _OLD_DEBUG_DIR
        if debug_dir.exists():
            try:
                # Check if it's a mount point
                output = subprocess.run([_MOUNTPOINT_CMD, _MOUNTPOINT_CHECK_FLAG, str(debug_dir)], capture_output=True)
                if output.returncode == 0:
                    result["bindfs_mount"] = str(debug_dir)
            except (FileNotFoundError, OSError):
                pass  # mountpoint command might not exist

        return result


__all__ = ["SetupService"]
