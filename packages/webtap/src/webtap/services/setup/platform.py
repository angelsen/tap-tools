"""Platform detection and path management using platformdirs."""

import platform
import shutil
from pathlib import Path

import platformdirs

APP_NAME = "webtap"

_APP_AUTHOR = "webtap"
_BIN_DIR_NAME = ".local/bin"
_TMP_RUNTIME_DIR = "/tmp"

# Supported browsers with their configurations (keyed by canonical ID)
SUPPORTED_BROWSERS = {
    "chrome": {
        "name": "Chrome",
        "wrapper": "chrome-debug",
        "config_dir": "google-chrome",
        "icon": "google-chrome",
        "wm_class": "Google-chrome",
        "executables": {
            "linux": ["google-chrome-stable", "google-chrome"],
            "darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        },
    },
    "edge": {
        "name": "Edge",
        "wrapper": "edge-debug",
        "config_dir": "microsoft-edge",
        "icon": "microsoft-edge",
        "wm_class": "Microsoft-edge",
        "executables": {
            "linux": ["microsoft-edge-stable"],
            "darwin": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
        },
    },
}

_PLATFORM_DARWIN = "Darwin"
_PLATFORM_LINUX = "Linux"

_MACOS_APPLICATIONS_DIR = "Applications"
_LINUX_APPLICATIONS_DIR = ".local/share/applications"


def get_platform_paths() -> dict[str, Path]:
    """Get platform-appropriate paths using platformdirs.

    Returns:
        Dictionary of paths for config, data, cache, runtime, and state directories.
    """
    dirs = platformdirs.PlatformDirs(APP_NAME, _APP_AUTHOR)

    paths = {
        "config_dir": Path(dirs.user_config_dir),  # ~/.config/webtap or ~/Library/Application Support/webtap
        "data_dir": Path(dirs.user_data_dir),  # ~/.local/share/webtap or ~/Library/Application Support/webtap
        "cache_dir": Path(dirs.user_cache_dir),  # ~/.cache/webtap or ~/Library/Caches/webtap
        "state_dir": Path(dirs.user_state_dir),  # ~/.local/state/webtap or ~/Library/Application Support/webtap
    }

    # Runtime dir (not available on all platforms)
    try:
        paths["runtime_dir"] = Path(dirs.user_runtime_dir)
    except AttributeError:
        # Fallback for platforms without runtime dir
        paths["runtime_dir"] = Path(_TMP_RUNTIME_DIR) / APP_NAME

    return paths


def get_browser_info(browser_id: str) -> dict | None:
    """Get browser configuration from canonical browser ID.

    Args:
        browser_id: Browser ID (e.g., 'chrome', 'edge')

    Returns:
        Browser info dict or None if not supported.
    """
    return SUPPORTED_BROWSERS.get(browser_id)


def detect_browsers() -> list[str]:
    """Detect installed supported browsers.

    Returns:
        List of browser IDs found on the system.
    """
    system = platform.system().lower()
    found = []
    for browser_id, config in SUPPORTED_BROWSERS.items():
        for exe in config.get("executables", {}).get(system, []):
            if exe.startswith("/"):
                if Path(exe).expanduser().exists():
                    found.append(browser_id)
                    break
            elif shutil.which(exe):
                found.append(browser_id)
                break
    return found


def find_browser_path(browser_id: str) -> str | None:
    """Find actual executable path for a browser.

    Args:
        browser_id: Browser ID (e.g., 'chrome', 'edge')

    Returns:
        Full path to browser executable or None if not found.
    """
    config = SUPPORTED_BROWSERS.get(browser_id)
    if not config:
        return None
    system = platform.system().lower()
    for exe in config.get("executables", {}).get(system, []):
        if exe.startswith("/"):
            path = Path(exe).expanduser()
            if path.exists():
                return str(path)
        elif found := shutil.which(exe):
            return found
    return None


def get_platform_info() -> dict:
    """Get comprehensive platform information.

    Returns:
        Dictionary with system info, paths, and capabilities.
    """
    system = platform.system()
    paths = get_platform_paths()

    # Unified paths for both platforms
    paths["bin_dir"] = Path.home() / _BIN_DIR_NAME

    # Platform-specific launcher locations
    if system == _PLATFORM_DARWIN:
        paths["applications_dir"] = Path.home() / _MACOS_APPLICATIONS_DIR
    else:  # Linux
        paths["applications_dir"] = Path.home() / _LINUX_APPLICATIONS_DIR

    return {
        "system": system.lower(),
        "is_macos": system == _PLATFORM_DARWIN,
        "is_linux": system == _PLATFORM_LINUX,
        "paths": paths,
        "capabilities": {
            "desktop_files": system == _PLATFORM_LINUX,
            "app_bundles": system == _PLATFORM_DARWIN,
            "bindfs": system == _PLATFORM_LINUX and shutil.which("bindfs") is not None,
        },
    }


def ensure_directories() -> None:
    """Ensure all required directories exist with proper permissions."""
    paths = get_platform_paths()

    for name, path in paths.items():
        if name != "runtime_dir":  # Runtime dir is often system-managed
            path.mkdir(parents=True, exist_ok=True, mode=0o755)

    # Ensure bin directory exists
    info = get_platform_info()
    info["paths"]["bin_dir"].mkdir(parents=True, exist_ok=True, mode=0o755)
