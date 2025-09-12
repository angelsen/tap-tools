"""Platform detection and path management using platformdirs."""

import platform
import shutil
from pathlib import Path
from typing import Optional

import platformdirs


def get_platform_paths() -> dict[str, Path]:
    """Get platform-appropriate paths using platformdirs.

    Returns:
        Dictionary of paths for config, data, cache, runtime, and state directories.
    """
    app_name = "webtap"
    app_author = "webtap"

    dirs = platformdirs.PlatformDirs(app_name, app_author)

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
        paths["runtime_dir"] = Path("/tmp") / app_name

    return paths


def get_chrome_path() -> Optional[Path]:
    """Find Chrome executable path for current platform.

    Returns:
        Path to Chrome executable or None if not found.
    """
    system = platform.system()

    if system == "Darwin":
        # macOS standard locations
        candidates = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    elif system == "Linux":
        # Linux standard locations
        candidates = [
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/snap/bin/chromium"),
        ]
    else:
        return None

    for path in candidates:
        if path.exists():
            return path

    # Try to find in PATH
    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
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
    paths["bin_dir"] = Path.home() / ".local/bin"  # User space, no sudo needed
    wrapper_name = "chrome-debug"  # Same name on both platforms

    # Platform-specific launcher locations
    if system == "Darwin":
        paths["applications_dir"] = Path.home() / "Applications"
    else:  # Linux
        paths["applications_dir"] = Path.home() / ".local/share/applications"

    chrome_path = get_chrome_path()

    return {
        "system": system.lower(),
        "is_macos": system == "Darwin",
        "is_linux": system == "Linux",
        "paths": paths,
        "chrome": {
            "path": chrome_path,
            "found": chrome_path is not None,
            "wrapper_name": wrapper_name,
        },
        "capabilities": {
            "desktop_files": system == "Linux",
            "app_bundles": system == "Darwin",
            "bindfs": system == "Linux" and shutil.which("bindfs") is not None,
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
