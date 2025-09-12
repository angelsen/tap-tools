"""Platform detection and path management using platformdirs."""

import platform
import shutil
from pathlib import Path
from typing import Optional

import platformdirs

# Application constants
APP_NAME = "webtap"
APP_AUTHOR = "webtap"

# Directory names
BIN_DIR_NAME = ".local/bin"
WRAPPER_NAME = "chrome-debug"
TMP_RUNTIME_DIR = "/tmp"

# Chrome executable names for Linux
CHROME_NAMES_LINUX = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
]

# Chrome paths for macOS
CHROME_PATHS_MACOS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # Relative to home
]

# Chrome paths for Linux
CHROME_PATHS_LINUX = [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
]

# Platform identifiers
PLATFORM_DARWIN = "Darwin"
PLATFORM_LINUX = "Linux"

# Application directories
MACOS_APPLICATIONS_DIR = "Applications"
LINUX_APPLICATIONS_DIR = ".local/share/applications"


def get_platform_paths() -> dict[str, Path]:
    """Get platform-appropriate paths using platformdirs.

    Returns:
        Dictionary of paths for config, data, cache, runtime, and state directories.
    """
    dirs = platformdirs.PlatformDirs(APP_NAME, APP_AUTHOR)

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
        paths["runtime_dir"] = Path(TMP_RUNTIME_DIR) / APP_NAME

    return paths


def get_chrome_path() -> Optional[Path]:
    """Find Chrome executable path for current platform.

    Returns:
        Path to Chrome executable or None if not found.
    """
    system = platform.system()

    if system == PLATFORM_DARWIN:
        # macOS standard locations
        candidates = [
            Path(CHROME_PATHS_MACOS[0]),
            Path.home() / CHROME_PATHS_MACOS[1],
        ]
    elif system == PLATFORM_LINUX:
        # Linux standard locations
        candidates = [Path(p) for p in CHROME_PATHS_LINUX]
    else:
        return None

    for path in candidates:
        if path.exists():
            return path

    # Try to find in PATH
    for name in CHROME_NAMES_LINUX:
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
    paths["bin_dir"] = Path.home() / BIN_DIR_NAME  # User space, no sudo needed

    # Platform-specific launcher locations
    if system == PLATFORM_DARWIN:
        paths["applications_dir"] = Path.home() / MACOS_APPLICATIONS_DIR
    else:  # Linux
        paths["applications_dir"] = Path.home() / LINUX_APPLICATIONS_DIR

    chrome_path = get_chrome_path()

    return {
        "system": system.lower(),
        "is_macos": system == PLATFORM_DARWIN,
        "is_linux": system == PLATFORM_LINUX,
        "paths": paths,
        "chrome": {
            "path": chrome_path,
            "found": chrome_path is not None,
            "wrapper_name": WRAPPER_NAME,
        },
        "capabilities": {
            "desktop_files": system == PLATFORM_LINUX,
            "app_bundles": system == PLATFORM_DARWIN,
            "bindfs": system == PLATFORM_LINUX and shutil.which("bindfs") is not None,
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
