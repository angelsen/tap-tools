"""Pane operations - all pane-related functionality.

PUBLIC API:
  - PaneInfo: Complete pane information data class
  - get_pane_pid: Get process ID for pane
  - get_pane_info: Get complete pane information
  - list_panes: List all panes with optional filtering
  - send_keys: Send keystrokes to pane
  - send_via_paste_buffer: Send content using paste buffer
  - capture_visible: Capture visible pane content
  - capture_last_n: Capture last N lines from pane
  - create_panes_with_layout: Create multiple panes with layout
"""

from typing import List, Optional
from dataclasses import dataclass
import json
import subprocess
import hashlib

from .core import run_tmux, _is_current_pane, _get_current_pane
from ._exceptions import CurrentPaneError, PaneNotFoundError
from ..types import SessionWindowPane


@dataclass
class PaneInfo:
    """Complete information about a tmux pane.

    Attributes:
        pane_id: Tmux pane ID (e.g., '%42').
        session: Session name.
        window_index: Window index.
        window_name: Window name.
        pane_index: Pane index.
        pane_title: Pane title.
        pane_pid: Process ID of pane.
        is_active: Whether pane is active in window.
        is_current: Whether pane is currently selected.
        swp: Session:window.pane format.
    """

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

    Works with any content including interactive commands with Claude.
    Supports control sequences, escape sequences, and text.

    Args:
        pane_id: Target pane ID.
        *commands: One or more commands/keys to send.
        enter: Whether to send Enter key after commands. Defaults to True.
        delay: Delay in seconds before sending Enter. Defaults to 0.05.

    Returns:
        True if successful.

    Raises:
        CurrentPaneError: If attempting to send to current pane.
    """
    if _is_current_pane(pane_id):
        raise CurrentPaneError(f"Cannot send commands to current pane ({pane_id})")

    if not commands:
        return True

    args = ["send-keys", "-t", pane_id]
    args.extend(commands)

    code, _, _ = run_tmux(args)
    if code != 0:
        return False

    if enter:
        if delay > 0:
            import time

            time.sleep(delay)
        code, _, _ = run_tmux(["send-keys", "-t", pane_id, "Enter"])
        return code == 0

    return True


def send_via_paste_buffer(pane_id: str, content: str, enter: bool = True, delay: float = 0.05) -> bool:
    """Send content using tmux paste buffer for multiline/special content.

    Args:
        pane_id: Target pane ID.
        content: Content to send (can be multiline).
        enter: Whether to send Enter key after content.
        delay: Delay in seconds before sending Enter.
    """
    if _is_current_pane(pane_id):
        raise CurrentPaneError(f"Cannot send to current pane ({pane_id})")

    buffer_name = f"tt_{hashlib.md5(content.encode()).hexdigest()[:8]}"

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

    code, _, stderr = run_tmux(["paste-buffer", "-t", pane_id, "-b", buffer_name, "-d", "-p"])

    if code != 0:
        raise RuntimeError(f"Failed to paste buffer: {stderr}")

    if enter:
        if delay > 0:
            import time

            time.sleep(delay)
        code, _, _ = run_tmux(["send-keys", "-t", pane_id, "Enter"])

    return code == 0


def get_pane_pid(pane_id: str) -> int:
    """Get the PID of a pane's process.

    Args:
        pane_id: Tmux pane ID.

    Returns:
        Process ID of the pane.

    Raises:
        PaneNotFoundError: If pane doesn't exist.
    """
    code, stdout, stderr = run_tmux(
        ["list-panes", "-t", pane_id, "-f", f"#{{==:#{{pane_id}},{pane_id}}}", "-F", "#{pane_pid}"]
    )

    if code != 0:
        raise PaneNotFoundError(f"Failed to get pane PID: {stderr}")

    try:
        return int(stdout.strip())
    except ValueError:
        raise RuntimeError(f"Failed to parse PID: invalid format '{stdout}'")


def __get_pane_session_window_pane(pane_id: str) -> SessionWindowPane:
    """Get session:window.pane format for pane ID."""
    code, stdout, stderr = run_tmux(
        ["display-message", "-p", "-t", pane_id, "#{session_name}:#{window_index}.#{pane_index}"]
    )

    if code != 0:
        raise PaneNotFoundError(f"Failed to get pane session:window.pane: {stderr}")

    return stdout.strip()


def get_pane_info(pane_id: str) -> PaneInfo:
    """Get detailed information for a specific pane.

    Args:
        pane_id: Tmux pane ID.

    Returns:
        Complete pane information.

    Raises:
        PaneNotFoundError: If pane doesn't exist.
    """
    format_str = "#{pane_id}:#{session_name}:#{window_index}:#{window_name}:#{pane_index}:#{pane_title}:#{pane_pid}:#{pane_active}"

    code, stdout, stderr = run_tmux(["list-panes", "-t", pane_id, "-F", format_str])
    if code != 0:
        raise PaneNotFoundError(f"Failed to get pane info: {stderr}")

    parts = stdout.strip().split(":")
    if len(parts) < 8:
        raise RuntimeError(f"Failed to parse pane info: invalid format '{stdout}'")

    current_pane_id = _get_current_pane()

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
    """List tmux panes with full information.

    Args:
        all: List all panes across all sessions.
        session: Session to filter by.
        window: Window to filter by.

    Returns:
        List of pane information objects.
    """
    cmd = ["list-panes"]

    if window:
        cmd.extend(["-t", window])
    elif session:
        cmd.extend(["-t", session])
    elif all:
        cmd.append("-a")

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
    current_pane_id = _get_current_pane()

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

    panes.sort(key=lambda p: (p.session, p.window_index, p.pane_index))
    return panes


def __strip_trailing_empty_lines(content: str) -> str:
    """Strip tmux pane height padding lines."""
    if not content:
        return ""

    lines = content.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        return "\n".join(lines) + "\n"
    return ""


def capture_visible(pane_id: str) -> str:
    """Capture visible content from pane.

    Args:
        pane_id: Tmux pane ID.

    Returns:
        Visible pane content.
    """
    code, stdout, _ = run_tmux(["capture-pane", "-t", pane_id, "-p"])
    return __strip_trailing_empty_lines(stdout) if code == 0 else ""


def _capture_all(pane_id: str) -> str:
    """Capture all history from pane."""
    code, stdout, _ = run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", "-"])
    return __strip_trailing_empty_lines(stdout) if code == 0 else ""


def capture_last_n(pane_id: str, lines: int) -> str:
    """Capture last N lines from pane."""
    code, stdout, _ = run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", f"-{lines}"])
    return __strip_trailing_empty_lines(stdout) if code == 0 else ""


def create_panes_with_layout(session: str, num_panes: int, layout: str = "even-horizontal") -> List[str]:
    """Create multiple panes in session with layout.

    Args:
        session: Session name.
        num_panes: Number of panes to create.
        layout: Tmux layout name.
    """
    if num_panes < 2:
        raise RuntimeError("Failed to create layout: need at least 2 panes")

    pane_ids = []

    code, stdout, _ = run_tmux(["list-panes", "-t", f"{session}:0", "-F", "#{pane_id}"])
    if code == 0:
        pane_ids.append(stdout.strip())

    for i in range(1, num_panes):
        code, stdout, _ = run_tmux(["split-window", "-t", f"{session}:0.{i - 1}", "-P", "-F", "#{pane_id}"])
        if code == 0:
            pane_ids.append(stdout.strip())

    __apply_layout(session, layout)

    return pane_ids


def __apply_layout(session: str, layout: str, window: int = 0) -> bool:
    """Apply layout to window.

    Args:
        session: Session name.
        layout: Layout name.
        window: Window index.
    """
    code, _, _ = run_tmux(["select-layout", "-t", f"{session}:{window}", layout])
    return code == 0
