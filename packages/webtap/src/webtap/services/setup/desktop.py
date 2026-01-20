"""Desktop entry and application launcher installation (cross-platform).

PUBLIC API:
  - DesktopSetupService: Install desktop launchers for browser wrappers
"""

import logging
from pathlib import Path
from typing import Any

from .platform import get_platform_info

logger = logging.getLogger(__name__)

_LINUX_DESKTOP_ENTRY = """[Desktop Entry]
Version=1.0
Type=Application
Name={browser_name} Debug
GenericName=Web Browser (Debug Mode)
Comment={browser_name} with remote debugging enabled
Icon={icon}
Categories=Development;WebBrowser;
MimeType=application/pdf;application/rdf+xml;application/rss+xml;application/xhtml+xml;application/xhtml_xml;application/xml;image/gif;image/jpeg;image/png;image/webp;text/html;text/xml;x-scheme-handler/ftp;x-scheme-handler/http;x-scheme-handler/https;
StartupWMClass={wm_class}
StartupNotify=true
Terminal=false
Exec={wrapper_path} %U
Actions=new-window;new-private-window;temp-profile;

[Desktop Action new-window]
Name=New Window
StartupWMClass={wm_class}
Exec={wrapper_path}

[Desktop Action new-private-window]
Name=New Incognito Window
StartupWMClass={wm_class}
Exec={wrapper_path} --incognito

[Desktop Action temp-profile]
Name=New Window (Temp Profile)
StartupWMClass={wm_class}
Exec={wrapper_path} --temp
"""

_MACOS_INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>{browser_name} Debug</string>
    <key>CFBundleIdentifier</key>
    <string>com.webtap.{wrapper}</string>
    <key>CFBundleName</key>
    <string>{browser_name} Debug</string>
    <key>CFBundleDisplayName</key>
    <string>{browser_name} Debug</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.12</string>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
        <string>x86_64</string>
    </array>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>HTML Document</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>public.html</string>
            </array>
        </dict>
        <dict>
            <key>CFBundleTypeName</key>
            <string>Web Location</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>public.url</string>
            </array>
        </dict>
    </array>
    <key>CFBundleURLTypes</key>
    <array>
        <dict>
            <key>CFBundleURLName</key>
            <string>Web site URL</string>
            <key>CFBundleURLSchemes</key>
            <array>
                <string>http</string>
                <string>https</string>
            </array>
        </dict>
    </array>
</dict>
</plist>"""


class DesktopSetupService:
    """Platform-appropriate GUI launcher setup."""

    def __init__(self):
        self.info = get_platform_info()
        self.paths = self.info["paths"]

    def install_launcher(self, browser_id: str, browser_config: dict, force: bool = False) -> dict[str, Any]:
        """Install platform-appropriate launcher for a browser.

        Args:
            browser_id: Browser ID (e.g., 'chrome', 'edge')
            browser_config: Browser configuration dict from SUPPORTED_BROWSERS
            force: Overwrite existing launcher

        Returns:
            Installation result
        """
        wrapper_name = browser_config["wrapper"]
        wrapper_path = self.paths["bin_dir"] / wrapper_name

        # Check if wrapper exists first
        if not wrapper_path.exists():
            return {
                "success": False,
                "message": f"Wrapper '{wrapper_name}' not found. Install wrapper first.",
                "path": None,
                "details": f"Expected wrapper at {wrapper_path}",
            }

        if self.info["is_macos"]:
            return self._install_macos_app(browser_config, wrapper_path, force)
        else:
            return self._install_linux_desktop(browser_config, wrapper_path, force)

    def _install_macos_app(self, browser_config: dict, wrapper_path: Path, force: bool) -> dict[str, Any]:
        """Create .app bundle for macOS.

        Args:
            browser_config: Browser configuration dict
            wrapper_path: Path to the wrapper script
            force: Overwrite existing app

        Returns:
            Installation result
        """
        import shutil

        browser_name = browser_config["name"]
        wrapper_name = browser_config["wrapper"]
        app_name = f"{browser_name} Debug.app"
        app_path = self.paths["applications_dir"] / app_name

        if app_path.exists() and not force:
            return {
                "success": False,
                "message": f"{browser_name} Debug app already exists",
                "path": str(app_path),
                "details": "Use --force to overwrite",
            }

        # Find browser path
        browser_path = shutil.which("google-chrome-stable" if "chrome" in wrapper_name else "microsoft-edge-stable")

        # Create app structure
        contents_dir = app_path / "Contents"
        macos_dir = contents_dir / "MacOS"
        macos_dir.mkdir(parents=True, exist_ok=True)

        # Create launcher script
        launcher_path = macos_dir / f"{browser_name} Debug"
        profile_dir = self.paths["data_dir"] / "profiles" / "default"

        launcher_content = f"""#!/bin/bash
# {browser_name} Debug app launcher - direct browser execution
# Avoids Rosetta warnings by directly launching browser

PORT=${{WEBTAP_PORT:-9222}}
PROFILE_DIR="{profile_dir}"
mkdir -p "$PROFILE_DIR"

# Launch browser directly with debugging
exec "{browser_path}" \\
    --remote-debugging-port="$PORT" \\
    --remote-allow-origins='*' \\
    --user-data-dir="$PROFILE_DIR" \\
    --no-first-run \\
    --no-default-browser-check \\
    "$@"
"""
        launcher_path.write_text(launcher_content)
        launcher_path.chmod(0o755)

        # Create Info.plist
        plist_path = contents_dir / "Info.plist"
        plist_content = _MACOS_INFO_PLIST.format(
            browser_name=browser_name,
            wrapper=wrapper_name,
        )
        plist_path.write_text(plist_content)

        logger.info(f"Created {browser_name} Debug app at {app_path}")

        return {
            "success": True,
            "message": f"{browser_name} Debug app created successfully",
            "path": str(app_path),
            "details": "Available in Launchpad and Spotlight search",
        }

    def _install_linux_desktop(self, browser_config: dict, wrapper_path: Path, force: bool) -> dict[str, Any]:
        """Install .desktop file for Linux.

        Args:
            browser_config: Browser configuration dict
            wrapper_path: Path to the wrapper script
            force: Overwrite existing desktop entry

        Returns:
            Installation result
        """
        browser_name = browser_config["name"]
        wrapper_name = browser_config["wrapper"]
        desktop_filename = f"{wrapper_name}.desktop"
        desktop_path = self.paths["applications_dir"] / desktop_filename

        if desktop_path.exists() and not force:
            return {
                "success": False,
                "message": f"Desktop entry '{desktop_filename}' already exists",
                "path": str(desktop_path),
                "details": "Use --force to overwrite",
            }

        # Create desktop entry with browser-specific values
        wrapper_abs_path = wrapper_path.expanduser()
        desktop_content = _LINUX_DESKTOP_ENTRY.format(
            browser_name=browser_name,
            icon=browser_config["icon"],
            wm_class=browser_config["wm_class"],
            wrapper_path=wrapper_abs_path,
        )

        # Create directory and save
        desktop_path.parent.mkdir(parents=True, exist_ok=True)
        desktop_path.write_text(desktop_content)
        desktop_path.chmod(0o644)

        logger.info(f"Installed desktop entry to {desktop_path}")

        return {
            "success": True,
            "message": f"Installed {browser_name} Debug desktop entry",
            "path": str(desktop_path),
            "details": f"Available in application menu as '{browser_name} Debug'",
        }


__all__ = ["DesktopSetupService"]
