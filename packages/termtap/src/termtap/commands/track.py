"""Track command - monitor process state changes over time.

PUBLIC API:
  - track: Monitor process state changes for handler development
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from ..app import app
from ..pane import Pane, get_process_info, read_output, process_scan
from ..tmux import resolve_or_create_target
from ..types import Target


def _collect_wait_channels(pane: Pane) -> list[str]:
    """Collect wait channels from process chain for debugging.

    Internal helper for track command's debugging needs.
    """
    wait_channels = []
    for proc in pane.process_chain:
        if proc.wait_channel:
            wait_channels.append(f"{proc.name}:{proc.wait_channel}")
    return wait_channels


@app.command(
    display="markdown",
    fastmcp={"enabled": False},  # Development tool, not exposed to MCP
)
def track(
    state,
    *commands: str,
    target: Target = "default",
    duration: float = 10.0,
    enter: bool = True,
) -> dict[str, Any]:
    """Track process state changes for handler development.

    Args:
        state: Application state (unused).
        *commands: Commands/keys to send.
        target: Target pane. Defaults to "default".
        duration: Tracking duration in seconds. Defaults to 10.0.
        enter: Whether to send Enter after commands. Defaults to True.

    Returns:
        Markdown formatted tracking report with analysis data.

    Examples:
        track("ls -la")  # Send command with Enter
        track("C-c", enter=False)  # Just Ctrl+C
        track("C-d", "C-d", enter=False)  # Two Ctrl+D keys
    """
    if duration <= 0 or duration > 300:
        return {
            "elements": [{"type": "text", "content": "Error: Duration must be between 0-300 seconds"}],
            "frontmatter": {"error": "Invalid duration", "status": "error"},
        }

    try:
        pane_id, session_window_pane = resolve_or_create_target(target)
    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    base_dir = Path.home() / ".termtap" / "tracking"
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    command_str = " ".join(commands) if commands else "empty"
    slug = re.sub(r"[^\w\s-]", "", command_str)[:50].strip().replace(" ", "_")
    tracking_dir = base_dir / f"{timestamp}_{slug}"
    tracking_dir.mkdir(exist_ok=True)
    (tracking_dir / "screenshots").mkdir(exist_ok=True)

    pane = Pane(pane_id)

    start_time = time.time()
    samples = []
    screenshots = {}  # hash -> (timestamp, content)

    # Capture initial state
    try:
        with process_scan(pane.pane_id):
            initial_info = get_process_info(pane)
            initial_screenshot = read_output(pane)
            initial_hash = hashlib.md5(initial_screenshot.encode()).hexdigest()

            samples.append(
                {
                    "elapsed": 0.0,
                    "process": initial_info["process"],
                    "shell": initial_info["shell"],
                    "ready": initial_info["ready"],
                    "state_description": initial_info["state_description"],
                    "handler": initial_info["handler"],
                    "process_tree": initial_info["process_tree"],
                    "wait_channels": _collect_wait_channels(pane),
                    "screenshot_hash": initial_hash,
                }
            )
            screenshots[initial_hash] = (0.0, initial_screenshot)
    except Exception:
        pass  # Continue even if initial capture fails

    try:
        if commands:
            # Cannot track current pane
            from ..tmux.core import run_tmux

            code, stdout, _ = run_tmux(["display-message", "-p", "#{pane_id}"])
            current_pane_id = stdout.strip() if code == 0 else None

            if pane_id == current_pane_id:
                return {
                    "elements": [{"type": "text", "content": f"Error: Cannot track in current pane ({pane_id})"}],
                    "frontmatter": {"error": "Cannot track current pane", "status": "error"},
                }

            # Send keys with minimal interference
            from ..tmux.pane import send_keys as tmux_send_keys

            # Keep default 50ms delay before Enter for commands to register properly
            if not tmux_send_keys(pane.pane_id, " ".join(commands), enter=enter):
                raise RuntimeError("Failed to send keys to pane")
    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    time.sleep(0.1)  # Let command start

    while time.time() - start_time < duration:
        elapsed = time.time() - start_time

        try:
            with process_scan(pane.pane_id):
                process_info = get_process_info(pane)
                screenshot = read_output(pane)
                screenshot_hash = hashlib.md5(screenshot.encode()).hexdigest()

                samples.append(
                    {
                        "elapsed": round(elapsed, 1),
                        "process": process_info["process"],
                        "shell": process_info["shell"],
                        "ready": process_info["ready"],
                        "state_description": process_info["state_description"],
                        "handler": process_info["handler"],
                        "process_tree": process_info["process_tree"],
                        "wait_channels": _collect_wait_channels(pane),
                        "screenshot_hash": screenshot_hash,
                    }
                )

                if screenshot_hash not in screenshots:
                    screenshots[screenshot_hash] = (elapsed, screenshot)

        except Exception:
            pass  # Continue tracking

        time.sleep(0.1)

    try:
        with process_scan(pane.pane_id):
            final_info = get_process_info(pane)
            final_screenshot = read_output(pane)
            final_hash = hashlib.md5(final_screenshot.encode()).hexdigest()

            samples.append(
                {
                    "elapsed": round(duration, 1),
                    "process": final_info["process"],
                    "shell": final_info["shell"],
                    "ready": final_info["ready"],
                    "state_description": final_info["state_description"],
                    "handler": final_info["handler"],
                    "process_tree": final_info["process_tree"],
                    "wait_channels": _collect_wait_channels(pane),
                    "screenshot_hash": final_hash,
                }
            )
            screenshots[final_hash] = (duration, final_screenshot)
    except Exception:
        pass

    import platform

    metadata = {
        "commands": list(commands),
        "enter": enter,
        "target": str(target),
        "duration": duration,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_samples": len(samples),
        "system": {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
    }
    (tracking_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (tracking_dir / "timeline.json").write_text(json.dumps(samples, indent=2))

    for hash_val, (ts, content) in screenshots.items():
        # Show special characters in debug format
        debug_lines = []
        for line in content.split("\n"):
            debug_lines.append(repr(line))

        (tracking_dir / "screenshots" / f"{ts:.1f}s.txt").write_text("\n".join(debug_lines))

    handlers_seen = sorted(set(s["handler"] for s in samples))

    commands_str = " ".join(commands) if commands else "(no commands)"

    elements = [
        {"type": "text", "content": f"Process tracked: `{commands_str}`"},
        {"type": "text", "content": f"Enter: {enter}"},
        {"type": "text", "content": f"Duration: {duration}s ({len(samples)} samples)"},
        {"type": "text", "content": f"Handlers: {', '.join(handlers_seen)}"},
        {"type": "text", "content": f"Screenshots: {len(screenshots)} unique"},
        {"type": "text", "content": ""},
        {"type": "text", "content": f"Data: `{tracking_dir}`"},
    ]

    return {
        "elements": elements,
        "frontmatter": {
            "command": "track",
            "status": "completed",
            "samples": len(samples),
        },
    }
