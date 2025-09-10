"""Chrome wrapper setup functionality for WebTap."""

import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def install_chrome_wrapper(force: bool = False) -> Dict[str, Any]:
    """Install Chrome wrapper script for debugging.

    Args:
        force: Overwrite existing script

    Returns:
        Dict with success, message, path, details
    """
    target_path = Path.home() / ".local" / "bin" / "wrappers" / "google-chrome-stable"

    if target_path.exists() and not force:
        return {
            "success": False,
            "message": "Chrome wrapper already exists",
            "path": str(target_path),
            "details": "Use --force to overwrite",
        }

    wrapper_script = """#!/bin/bash
# Chrome wrapper using bindfs for perfect state sync with debug port

DEBUG_DIR="$HOME/.config/google-chrome-debug"
REAL_DIR="$HOME/.config/google-chrome"

# Check if bindfs is installed
if ! command -v bindfs &>/dev/null; then
    echo "Error: bindfs not installed. Install with: yay -S bindfs" >&2
    exit 1
fi

# Mount real profile via bindfs if not already mounted
if ! mountpoint -q "$DEBUG_DIR" 2>/dev/null; then
    mkdir -p "$DEBUG_DIR"
    if ! bindfs --no-allow-other "$REAL_DIR" "$DEBUG_DIR"; then
        echo "Error: Failed to mount Chrome profile via bindfs" >&2
        exit 1
    fi
    echo "Chrome debug profile mounted. To unmount: fusermount -u $DEBUG_DIR" >&2
fi

# Launch Chrome with debugging on bindfs mount
exec /usr/bin/google-chrome-stable \\
    --remote-debugging-port=9222 \\
    --remote-allow-origins='*' \\
    --user-data-dir="$DEBUG_DIR" \\
    "$@"
"""

    # Create directory and save
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(wrapper_script)
    target_path.chmod(0o755)  # Make executable

    # Check PATH
    path_dirs = os.environ.get("PATH", "").split(":")
    wrapper_dir = str(target_path.parent)
    in_path = wrapper_dir in path_dirs

    logger.info(f"Installed Chrome wrapper to {target_path}")

    return {
        "success": True,
        "message": "Installed Chrome wrapper script",
        "path": str(target_path),
        "details": "Already in PATH ✓" if in_path else "Add to PATH",
    }
