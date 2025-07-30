"""Track command - monitor process state changes over time."""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from replkit2.textkit import markdown

from ..app import app
from ..types import Target
from ..tmux import (
    send_keys,
    resolve_or_create_target,
    CurrentPaneError,
    capture_visible,
)
from ..process.detector import detect_process
from ..errors import markdown_error_response


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "description": "Track process state changes over time"},
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
        *commands: Commands/keys to send (can be multiple)
        target: Target pane (default: "default")
        duration: How long to track in seconds (default: 10.0)
        enter: Whether to send Enter after commands (default: True)

    Returns:
        Summary report pointing to tracking data

    Examples:
        track("ls -la")  # Send command with Enter
        track("C-c", enter=False)  # Just Ctrl+C
        track("C-d", "C-d", enter=False)  # Two Ctrl+D keys
    """
    # Validate
    if duration <= 0 or duration > 300:
        return markdown_error_response("Duration must be between 0-300 seconds")

    # Setup
    try:
        pane_id, session_window_pane = resolve_or_create_target(target)
    except Exception as e:
        return markdown_error_response(f"Target error: {str(e)}")

    # Create tracking directory
    base_dir = Path.home() / ".termtap" / "tracking"
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    # Create slug from commands
    command_str = " ".join(commands) if commands else "empty"
    slug = re.sub(r"[^\w\s-]", "", command_str)[:50].strip().replace(" ", "_")
    tracking_dir = base_dir / f"{timestamp}_{slug}"
    tracking_dir.mkdir(exist_ok=True)
    (tracking_dir / "screenshots").mkdir(exist_ok=True)

    # Track
    start_time = time.time()
    samples = []
    screenshots = {}  # hash -> (timestamp, content)

    # Capture initial state before sending command
    try:
        initial_info = detect_process(pane_id)
        initial_screenshot = capture_visible(pane_id)
        initial_hash = hashlib.md5(initial_screenshot.encode()).hexdigest()

        samples.append(
            {
                "elapsed": 0.0,
                "state": initial_info.state,
                "wait_channel": initial_info.wait_channel,
                "process": initial_info.process,
                "shell": initial_info.shell,
                "screenshot_hash": initial_hash,
            }
        )
        screenshots[initial_hash] = (0.0, initial_screenshot)
    except Exception:
        pass  # Continue even if initial capture fails

    # Send commands
    try:
        if commands:
            send_keys(pane_id, *commands, enter=enter)
    except CurrentPaneError:
        return markdown_error_response(f"Cannot track in current pane ({pane_id})")
    except Exception as e:
        return markdown_error_response(str(e))

    time.sleep(0.1)  # Let command start

    # Sample every 100ms
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time

        try:
            # Sample
            process_info = detect_process(pane_id)
            screenshot = capture_visible(pane_id)
            screenshot_hash = hashlib.md5(screenshot.encode()).hexdigest()

            samples.append(
                {
                    "elapsed": round(elapsed, 1),
                    "state": process_info.state,
                    "wait_channel": process_info.wait_channel,
                    "process": process_info.process,
                    "shell": process_info.shell,
                    "screenshot_hash": screenshot_hash,
                }
            )

            # Store unique screenshots
            if screenshot_hash not in screenshots:
                screenshots[screenshot_hash] = (elapsed, screenshot)

        except Exception:
            pass  # Continue tracking

        time.sleep(0.1)

    # Final sample
    try:
        final_info = detect_process(pane_id)
        final_screenshot = capture_visible(pane_id)
        samples.append(
            {
                "elapsed": round(duration, 1),
                "state": final_info.state,
                "wait_channel": final_info.wait_channel,
                "process": final_info.process,
                "shell": final_info.shell,
                "screenshot_hash": hashlib.md5(final_screenshot.encode()).hexdigest(),
            }
        )
        screenshots[samples[-1]["screenshot_hash"]] = (duration, final_screenshot)
    except Exception:
        pass

    # Save data
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

    # Save screenshots with visible special characters for handler development
    for hash_val, (ts, content) in screenshots.items():
        # Convert to repr format to show special characters
        debug_lines = []
        for line in content.split("\n"):
            debug_lines.append(repr(line))

        (tracking_dir / "screenshots" / f"{ts:.1f}s.txt").write_text("\n".join(debug_lines))

    # Quick analysis
    wait_channels = sorted(set(s.get("wait_channel") for s in samples if s.get("wait_channel")))
    states = {}
    for sample in samples:
        key = (sample["state"], sample.get("wait_channel"))
        states[key] = states.get(key, 0) + 1

    # Return summary
    commands_str = " ".join(commands) if commands else "(no commands)"
    return (
        markdown()
        .text(f"Process tracked: `{commands_str}`")
        .text(f"Enter: {enter}")
        .text(f"Duration: {duration}s ({len(samples)} samples)")
        .text(f"Wait channels: {', '.join(wait_channels) if wait_channels else 'none'}")
        .text(f"Screenshots: {len(screenshots)} unique")
        .text("")
        .text(f"Data: `{tracking_dir}`")
        .build()
    )
