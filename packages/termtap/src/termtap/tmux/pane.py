"""Pane operations - all pane-related functionality."""

from typing import List, Optional
from dataclasses import dataclass
import json
import subprocess
import hashlib

from .core import run_tmux, is_current_pane, get_current_pane
from .exceptions import CurrentPaneError, PaneNotFoundError
from ..types import SessionWindowPane


@dataclass
class PaneInfo:
    """Complete information about a tmux pane."""

    pane_id: str  # %42
    session: str
    window_index: int
    window_name: str
    pane_index: int
    pane_title: str
    pane_pid: int
    is_active: bool
    is_current: bool
    swp: SessionWindowPane  # session:window.pane


def send_keys(pane_id: str, *commands, enter: bool = True, delay: float = 0.05) -> bool:
    """Send keystrokes to a pane.

    Args:
        pane_id: Target pane ID
        *commands: One or more commands/keys to send
        enter: Whether to send Enter key after commands
        delay: Delay in seconds before sending Enter (default: 0.05)

    Returns:
        True if successful

    Raises:
        CurrentPaneError: If attempting to send to current pane

    Examples:
        send_keys("pane", "ls -la")  # Text + 50ms + Enter
        send_keys("pane", "what is 2+2")  # Works with Claude!
        send_keys("pane", "text", delay=0)  # Immediate Enter
        send_keys("pane", "C-c", enter=False)  # Just Ctrl+C
        send_keys("pane", "Escape", "Escape")  # Multiple special keys
        send_keys("pane", "C-u", "new text")  # Clear + text
    """
    if is_current_pane(pane_id):
        raise CurrentPaneError(f"Cannot send commands to current pane ({pane_id})")

    if not commands:
        return True  # Nothing to send

    # Build args - each command is a separate argument
    args = ["send-keys", "-t", pane_id]
    args.extend(commands)

    # Send the commands
    code, _, _ = run_tmux(args)
    if code != 0:
        return False

    # Handle Enter with optional delay
    if enter:
        if delay > 0:
            import time

            time.sleep(delay)
        code, _, _ = run_tmux(["send-keys", "-t", pane_id, "Enter"])
        return code == 0

    return True


def send_via_paste_buffer(pane_id: str, content: str, enter: bool = True, delay: float = 0.05) -> bool:
    """Send content to pane using tmux paste buffer (reliable for multiline/special content).

    Args:
        pane_id: Target pane ID
        content: Content to send (can be multiline)
        enter: Whether to send Enter key after content
        delay: Delay in seconds before sending Enter (default: 0.05)

    Returns:
        True if successful

    Raises:
        CurrentPaneError: If attempting to send to current pane
        RuntimeError: If buffer operations fail
    """
    if is_current_pane(pane_id):
        raise CurrentPaneError(f"Cannot send to current pane ({pane_id})")

    # Generate deterministic buffer name from content hash
    buffer_name = f"tt_{hashlib.md5(content.encode()).hexdigest()[:8]}"

    # Load buffer via stdin
    proc = subprocess.Popen(
        ["tmux", "load-buffer", "-b", buffer_name, "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _, stderr = proc.communicate(input=content)

    if proc.returncode != 0:
        raise RuntimeError(f"Failed to load buffer: {stderr}")

    # Paste with auto-delete
    code, _, stderr = run_tmux(["paste-buffer", "-t", pane_id, "-b", buffer_name, "-d"])

    if code != 0:
        raise RuntimeError(f"Failed to paste buffer: {stderr}")

    if enter:
        if delay > 0:
            import time

            time.sleep(delay)
        code, _, _ = run_tmux(["send-keys", "-t", pane_id, "Enter"])

    return code == 0


def get_pane_pid(pane_id: str) -> int:
    """Get the PID of a pane's process."""
    # Use filter to get only the specific pane
    code, stdout, stderr = run_tmux(
        ["list-panes", "-t", pane_id, "-f", f"#{{==:#{{pane_id}},{pane_id}}}", "-F", "#{pane_pid}"]
    )

    if code != 0:
        raise PaneNotFoundError(f"Failed to get pane PID: {stderr}")

    try:
        return int(stdout.strip())
    except ValueError:
        raise RuntimeError(f"Failed to parse PID: invalid format '{stdout}'")


def get_pane_session_window_pane(pane_id: str) -> SessionWindowPane:
    """Get session:window.pane format for a pane ID.

    Args:
        pane_id: Tmux pane ID (e.g., '%0')

    Returns:
        Session window pane format (e.g., 'mysession:0.0')

    Raises:
        PaneNotFoundError: If pane doesn't exist
    """
    code, stdout, stderr = run_tmux(
        ["display-message", "-p", "-t", pane_id, "#{session_name}:#{window_index}.#{pane_index}"]
    )

    if code != 0:
        raise PaneNotFoundError(f"Failed to get pane session:window.pane: {stderr}")

    return stdout.strip()


def get_pane_info(pane_id: str) -> PaneInfo:
    """Get detailed information for a specific pane."""
    format_str = "#{pane_id}:#{session_name}:#{window_index}:#{window_name}:#{pane_index}:#{pane_title}:#{pane_pid}:#{pane_active}"

    code, stdout, stderr = run_tmux(["list-panes", "-t", pane_id, "-F", format_str])
    if code != 0:
        raise PaneNotFoundError(f"Failed to get pane info: {stderr}")

    parts = stdout.strip().split(":")
    if len(parts) < 8:
        raise RuntimeError(f"Failed to parse pane info: invalid format '{stdout}'")

    current_pane_id = get_current_pane()

    return PaneInfo(
        pane_id=parts[0],
        session=parts[1],
        window_index=int(parts[2]),
        window_name=parts[3] or str(parts[2]),
        pane_index=int(parts[4]),
        pane_title=parts[5],
        pane_pid=int(parts[6]),
        is_active=parts[7] == "1",
        is_current=parts[0] == current_pane_id,
        swp=f"{parts[1]}:{parts[2]}.{parts[4]}",
    )


def list_panes(all: bool = True, session: Optional[str] = None, window: Optional[str] = None) -> List[PaneInfo]:
    """List tmux panes with full information."""
    cmd = ["list-panes"]

    if window:
        cmd.extend(["-t", window])
    elif session:
        cmd.extend(["-t", session])
    elif all:
        cmd.append("-a")

    # Build JSON-like format for reliable parsing
    fields = {
        "pane_id": "#{pane_id}",
        "session_name": "#{session_name}",
        "window_index": "#{window_index}",
        "window_name": "#{window_name}",
        "pane_index": "#{pane_index}",
        "pane_title": "#{pane_title}",
        "pane_pid": "#{pane_pid}",
        "pane_active": "#{pane_active}",
    }
    format_parts = [f'"{k}":"{v}"' for k, v in fields.items()]
    format_str = "{" + ",".join(format_parts) + "}"

    cmd.extend(["-F", format_str])

    code, stdout, _ = run_tmux(cmd)
    if code != 0:
        return []

    panes = []
    current_pane_id = get_current_pane()

    for line in stdout.strip().split("\n"):
        if not line:
            continue

        try:
            data = json.loads(line)

            window_idx = int(data["window_index"])
            pane_idx = int(data["pane_index"])

            panes.append(
                PaneInfo(
                    pane_id=data["pane_id"],
                    session=data["session_name"],
                    window_index=window_idx,
                    window_name=data["window_name"] or str(window_idx),
                    pane_index=pane_idx,
                    pane_title=data["pane_title"],
                    pane_pid=int(data["pane_pid"]),
                    is_active=data["pane_active"] == "1",
                    is_current=data["pane_id"] == current_pane_id,
                    swp=f"{data['session_name']}:{window_idx}.{pane_idx}",
                )
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    # Sort by session, window, pane
    panes.sort(key=lambda p: (p.session, p.window_index, p.pane_index))
    return panes


def _strip_trailing_empty_lines(content: str) -> str:
    """Strip trailing empty lines that tmux adds to fill pane height.

    Preserves empty lines within the content but removes padding at the end.
    """
    if not content:
        return ""

    lines = content.splitlines()
    # Remove trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    # Preserve original line ending if content had one
    if lines:
        return "\n".join(lines) + "\n"
    return ""


def capture_visible(pane_id: str) -> str:
    """Capture visible content from pane."""
    code, stdout, _ = run_tmux(["capture-pane", "-t", pane_id, "-p"])
    return _strip_trailing_empty_lines(stdout) if code == 0 else ""


def capture_all(pane_id: str) -> str:
    """Capture all history from pane."""
    code, stdout, _ = run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", "-"])
    return _strip_trailing_empty_lines(stdout) if code == 0 else ""


def capture_last_n(pane_id: str, lines: int) -> str:
    """Capture last N lines from pane."""
    code, stdout, _ = run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", f"-{lines}"])
    return _strip_trailing_empty_lines(stdout) if code == 0 else ""


def create_panes_with_layout(session: str, num_panes: int, layout: str = "even-horizontal") -> List[str]:
    """Create multiple panes in a session with layout.

    Returns:
        List of pane IDs
    """
    if num_panes < 2:
        raise RuntimeError("Failed to create layout: need at least 2 panes")

    pane_ids = []

    # Get first pane
    code, stdout, _ = run_tmux(["list-panes", "-t", f"{session}:0", "-F", "#{pane_id}"])
    if code == 0:
        pane_ids.append(stdout.strip())

    # Create additional panes
    for i in range(1, num_panes):
        code, stdout, _ = run_tmux(["split-window", "-t", f"{session}:0.{i - 1}", "-P", "-F", "#{pane_id}"])
        if code == 0:
            pane_ids.append(stdout.strip())

    # Apply layout
    apply_layout(session, layout)

    return pane_ids


def apply_layout(session: str, layout: str, window: int = 0) -> bool:
    """Apply layout to window."""
    code, _, _ = run_tmux(["select-layout", "-t", f"{session}:{window}", layout])
    return code == 0
