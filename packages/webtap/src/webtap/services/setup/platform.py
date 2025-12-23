"""Platform detection and path management using platformdirs."""

import platform
import shutil
from pathlib import Path
from typing import Optional

import platformdirs

APP_NAME = "webtap"

_APP_AUTHOR = "webtap"
_BIN_DIR_NAME = ".local/bin"
_WRAPPER_NAME = "chrome-debug"
_TMP_RUNTIME_DIR = "/tmp"

_CHROME_NAMES_LINUX = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
]

_CHROME_PATHS_MACOS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

_CHROME_PATHS_LINUX = [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
]

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


def get_chrome_path() -> Optional[Path]:
    """Find Chrome executable path for current platform.

    Returns:
        Path to Chrome executable or None if not found.
    """
    system = platform.system()

    if system == _PLATFORM_DARWIN:
        # macOS standard locations
        candidates = [
            Path(_CHROME_PATHS_MACOS[0]),
            Path.home() / _CHROME_PATHS_MACOS[1],
        ]
    elif system == _PLATFORM_LINUX:
        # Linux standard locations
        candidates = [Path(p) for p in _CHROME_PATHS_LINUX]
    else:
        return None

    for path in candidates:
        if path.exists():
            return path

    # Try to find in PATH
    for name in _CHROME_NAMES_LINUX:
        if found := shutil.which(name):
            return Path(found)

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

    chrome_path = get_chrome_path()

    return {
        "system": system.lower(),
        "is_macos": system == _PLATFORM_DARWIN,
        "is_linux": system == _PLATFORM_LINUX,
        "paths": paths,
        "chrome": {
            "path": chrome_path,
            "found": chrome_path is not None,
            "wrapper_name": _WRAPPER_NAME,
        },
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
