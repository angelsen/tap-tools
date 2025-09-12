"""Desktop/Application launcher setup (cross-platform)."""

import logging
from typing import Dict, Any

from .platform import get_platform_info

logger = logging.getLogger(__name__)

# Desktop entry template for Linux
LINUX_DESKTOP_ENTRY = """[Desktop Entry]
Version=1.0
Type=Application
Name=Chrome Debug
GenericName=Web Browser (Debug Mode)
Comment=Chrome with remote debugging enabled
Icon=google-chrome
Categories=Development;WebBrowser;
MimeType=application/pdf;application/rdf+xml;application/rss+xml;application/xhtml+xml;application/xhtml_xml;application/xml;image/gif;image/jpeg;image/png;image/webp;text/html;text/xml;x-scheme-handler/ftp;x-scheme-handler/http;x-scheme-handler/https;
StartupWMClass=Google-chrome
StartupNotify=true
Terminal=false
Exec={wrapper_path} %U
Actions=new-window;new-private-window;temp-profile;

[Desktop Action new-window]
Name=New Window
StartupWMClass=Google-chrome
Exec={wrapper_path}

[Desktop Action new-private-window]
Name=New Incognito Window
StartupWMClass=Google-chrome
Exec={wrapper_path} --incognito

[Desktop Action temp-profile]
Name=New Window (Temp Profile)
StartupWMClass=Google-chrome
Exec={wrapper_path} --temp
"""

# Info.plist template for macOS app bundle
MACOS_INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Chrome Debug</string>
    <key>CFBundleIdentifier</key>
    <string>com.webtap.chrome-debug</string>
    <key>CFBundleName</key>
    <string>Chrome Debug</string>
    <key>CFBundleDisplayName</key>
    <string>Chrome Debug</string>
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
        self.chrome = self.info["chrome"]

        # Unified wrapper path: ~/.local/bin/chrome-debug
        self.wrapper_name = self.chrome["wrapper_name"]  # chrome-debug
        self.wrapper_path = self.paths["bin_dir"] / self.wrapper_name

    def install_launcher(self, force: bool = False) -> Dict[str, Any]:
        """Install platform-appropriate launcher.

        Args:
            force: Overwrite existing launcher

        Returns:
            Installation result
        """
        # Check if wrapper exists first
        if not self.wrapper_path.exists():
            return {
                "success": False,
                "message": "Chrome wrapper 'chrome-debug' not found. Run 'setup-chrome' first",
                "path": None,
                "details": f"Expected wrapper at {self.wrapper_path}",
            }

        if self.info["is_macos"]:
            return self._install_macos_app(force)
        else:
            return self._install_linux_desktop(force)

    def _install_macos_app(self, force: bool) -> Dict[str, Any]:
        """Create .app bundle for macOS.

        Args:
            force: Overwrite existing app

        Returns:
            Installation result
        """
        app_path = self.paths["applications_dir"] / "Chrome Debug.app"

        if app_path.exists() and not force:
            return {
                "success": False,
                "message": "Chrome Debug app already exists",
                "path": str(app_path),
                "details": "Use --force to overwrite",
            }

        # Create app structure
        contents_dir = app_path / "Contents"
        macos_dir = contents_dir / "MacOS"
        macos_dir.mkdir(parents=True, exist_ok=True)

        # Create launcher script that directly launches Chrome
        # This avoids Rosetta warnings from nested bash scripts
        launcher_path = macos_dir / "Chrome Debug"

        # Get Chrome path from platform info
        chrome_path = self.chrome["path"]
        profile_dir = self.paths["data_dir"] / "profiles" / "default"

        launcher_content = f"""#!/bin/bash
# Chrome Debug app launcher - direct Chrome execution
# Avoids Rosetta warnings by directly launching Chrome

PORT=${{WEBTAP_PORT:-9222}}
PROFILE_DIR="{profile_dir}"
mkdir -p "$PROFILE_DIR"

# Launch Chrome directly with debugging
exec "{chrome_path}" \\
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
        plist_path.write_text(MACOS_INFO_PLIST)

        logger.info(f"Created Chrome Debug app at {app_path}")

        return {
            "success": True,
            "message": "Chrome Debug app created successfully",
            "path": str(app_path),
            "details": "Available in Launchpad and Spotlight search",
        }

    def _install_linux_desktop(self, force: bool) -> Dict[str, Any]:
        """Install .desktop file for Linux.

        Args:
            force: Overwrite existing desktop entry

        Returns:
            Installation result
        """
        # Create separate Chrome Debug desktop entry (doesn't override system Chrome)
        desktop_path = self.paths["applications_dir"] / "chrome-debug.desktop"

        if desktop_path.exists() and not force:
            return {
                "success": False,
                "message": "Desktop entry already exists",
                "path": str(desktop_path),
                "details": "Use --force to overwrite",
            }

        # Create Chrome Debug desktop entry
        desktop_content = self._create_chrome_debug_desktop()

        # Create directory and save
        desktop_path.parent.mkdir(parents=True, exist_ok=True)
        desktop_path.write_text(desktop_content)
        desktop_path.chmod(0o644)  # Standard permissions for desktop files

        logger.info(f"Installed desktop entry to {desktop_path}")

        return {
            "success": True,
            "message": "Installed Chrome Debug desktop entry",
            "path": str(desktop_path),
            "details": "Available in application menu as 'Chrome Debug'",
        }

    def _create_chrome_debug_desktop(self) -> str:
        """Create Chrome Debug desktop entry with absolute paths."""
        # Use absolute expanded path for Exec lines
        wrapper_abs_path = self.wrapper_path.expanduser()

        return LINUX_DESKTOP_ENTRY.format(wrapper_path=wrapper_abs_path)
