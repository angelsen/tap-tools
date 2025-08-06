"""Track command - monitor process state changes over time.

PUBLIC API:
  - track: Monitor process state changes for handler development
"""

import hashlib
import json
import platform
import re
import time
from pathlib import Path
from typing import Any

from ..app import app
from ..pane import Pane, process_scan
from ..tmux import resolve_or_create_target
from ..types import Target


def _capture_raw_state(pane: Pane) -> dict:
    """Capture raw pane state without handler interpretation."""
    from ..tmux.pane import capture_visible

    screenshot = capture_visible(pane.pane_id)
    wait_channels = [f"{p.name}:{p.wait_channel}" for p in pane.process_chain if p.wait_channel]

    return {
        "pane_id": pane.pane_id,
        "session_window_pane": pane.session_window_pane,
        "pid": pane.pid,
        "shell": pane.shell.name if pane.shell else None,
        "process": pane.process.name if pane.process else None,
        "process_tree": [p.name for p in pane.process_chain],
        "wait_channels": wait_channels,
        "handler": type(pane.handler).__name__,
        "raw_handler_ready": pane.handler.is_ready(pane),
        "screenshot": screenshot,
        "screenshot_hash": hashlib.md5(screenshot.encode()).hexdigest(),
    }


def _collect_sample(pane: Pane, elapsed: float) -> dict:
    """Collect single tracking sample with timestamp."""
    state = _capture_raw_state(pane)

    return {
        "elapsed": round(elapsed, 1),
        "process": state["process"],
        "shell": state["shell"],
        "ready": state["raw_handler_ready"][0],
        "state_description": state["raw_handler_ready"][1],
        "handler": state["handler"],
        "process_tree": state["process_tree"],
        "wait_channels": state["wait_channels"],
        "screenshot_hash": state["screenshot_hash"],
        "screenshot": state["screenshot"],
    }


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
    """Track process state changes using raw system APIs.

    Ruthlessly direct implementation for maximum debugging accuracy.
    Returns minimal info - detailed data saved to tracking directory.

    Args:
        state: Application state (unused).
        *commands: Commands/keys to send.
        target: Target pane. Defaults to "default".
        duration: Tracking duration in seconds. Defaults to 10.0.
        enter: Whether to send Enter after commands. Defaults to True.

    Returns:
        Minimal markdown report - full data in ~/.termtap/tracking/
    """
    if duration <= 0 or duration > 300:
        return {
            "elements": [{"type": "text", "content": "Duration must be 0-300 seconds"}],
            "frontmatter": {"error": "Invalid duration", "status": "error"},
        }

    try:
        pane_id, _ = resolve_or_create_target(target)
    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    # Setup tracking directory
    base_dir = Path.home() / ".termtap" / "tracking"
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    command_str = " ".join(commands) if commands else "idle"
    slug = re.sub(r"[^\w\s-]", "", command_str)[:30].strip().replace(" ", "_")
    tracking_dir = base_dir / f"{timestamp}_{slug}"
    tracking_dir.mkdir(exist_ok=True)
    (tracking_dir / "screenshots").mkdir(exist_ok=True)

    pane = Pane(pane_id)
    start_time = time.time()
    samples = []
    screenshots = {}  # hash -> (timestamp, content)

    # DEFINITIVE: Capture initial state
    try:
        with process_scan(pane.pane_id):
            sample = _collect_sample(pane, 0.0)
            samples.append({k: v for k, v in sample.items() if k != "screenshot"})
            screenshots[sample["screenshot_hash"]] = (0.0, sample["screenshot"])
    except Exception:
        pass

    # Send commands if specified
    if commands:
        try:
            # Check not tracking current pane
            from ..tmux.core import run_tmux

            code, stdout, _ = run_tmux(["display-message", "-p", "#{pane_id}"])
            if code == 0 and pane_id == stdout.strip():
                return {
                    "elements": [{"type": "text", "content": f"Cannot track current pane ({pane_id})"}],
                    "frontmatter": {"error": "Current pane", "status": "error"},
                }

            # Direct tmux key sending
            from ..tmux.pane import send_keys as tmux_send_keys

            if not tmux_send_keys(pane.pane_id, " ".join(commands), enter=enter):
                raise RuntimeError("Failed to send keys")
        except Exception as e:
            return {
                "elements": [{"type": "text", "content": f"Send error: {e}"}],
                "frontmatter": {"error": str(e), "status": "error"},
            }

        time.sleep(0.1)  # Command startup

    # ROLLING: Track changes
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time
        try:
            with process_scan(pane.pane_id):
                sample = _collect_sample(pane, elapsed)
                samples.append({k: v for k, v in sample.items() if k != "screenshot"})

                # Only store unique screenshots
                if sample["screenshot_hash"] not in screenshots:
                    screenshots[sample["screenshot_hash"]] = (elapsed, sample["screenshot"])
        except Exception:
            pass
        time.sleep(0.1)

    # DEFINITIVE: Capture final state
    try:
        with process_scan(pane.pane_id):
            sample = _collect_sample(pane, duration)
            samples.append({k: v for k, v in sample.items() if k != "screenshot"})
            screenshots[sample["screenshot_hash"]] = (duration, sample["screenshot"])
    except Exception:
        pass

    # Save data to files
    metadata = {
        "commands": list(commands),
        "enter": enter,
        "target": str(target),
        "duration": duration,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "samples": len(samples),
        "screenshots": len(screenshots),
        "system": {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
    }

    (tracking_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (tracking_dir / "timeline.json").write_text(json.dumps(samples, indent=2))

    # Save screenshots with debug formatting
    for hash_val, (ts, content) in screenshots.items():
        debug_content = "\n".join(repr(line) for line in content.split("\n"))
        (tracking_dir / "screenshots" / f"{ts:.1f}s.txt").write_text(debug_content)

    # Minimal return - data is in directory
    handlers = sorted(set(s["handler"] for s in samples))
    cmd_desc = " ".join(commands) if commands else "idle"

    return {
        "elements": [
            {"type": "text", "content": f"**Tracked:** `{cmd_desc}`"},
            {
                "type": "text",
                "content": f"**Duration:** {duration}s • **Samples:** {len(samples)} • **Screenshots:** {len(screenshots)}",
            },
            {"type": "text", "content": f"**Handlers:** {', '.join(handlers)}"},
            {"type": "text", "content": f"**Data:** `{tracking_dir}`"},
        ],
        "frontmatter": {"command": "track", "status": "completed", "data_dir": str(tracking_dir)},
    }
