"""Pane operations - all pane-related functionality.

PUBLIC API:
  - PaneInfo: Complete pane information data class
  - list_panes: List all panes with full information
  - get_pane: Get single pane by ID
  - get_client_for_pane: Get client name for a pane
  - validate_pane_id: Validate pane ID format and existence
  - get_pane_pid: Get process ID for pane
  - send_keys: Send keystrokes to pane
  - send_via_paste_buffer: Send content using paste buffer
  - capture_visible: Capture visible pane content
  - capture_last_n: Capture last N lines from pane
  - create_panes_with_layout: Create multiple panes with layout
  - build_client_context: Build client context from tmux environment
"""

from dataclasses import dataclass
import json
import os
import subprocess
import hashlib
import warnings

from .core import run_tmux, _get_current_pane, _is_current_pane
from ._exceptions import PaneNotFoundError, CurrentPaneError
from ..types import LineEnding

# Type alias for session:window.pane format
SessionWindowPane = str


@dataclass
class PaneInfo:
    """Complete information about a tmux pane.

    Attributes:
        pane_id: Tmux pane ID (e.g., '%42').
        session: Session name.
        window_id: Tmux window ID (e.g., '@3').
        window_index: Window index.
        window_name: Window name.
        pane_index: Pane index.
        pane_title: Pane title.
        pane_pid: Process ID of pane.
        pane_current_command: Current process name (e.g., 'bash', 'python').
        is_active: Whether pane is active in window.
        is_current: Whether pane is currently selected.
        swp: Session:window.pane format.
    """

    pane_id: str  # %42
    session: str
    window_id: str  # @3
    window_index: int
    window_name: str
    pane_index: int
    pane_title: str
    pane_pid: int
    pane_current_command: str
    is_active: bool
    is_current: bool
    swp: SessionWindowPane  # session:window.pane


def build_client_context() -> dict[str, str]:
    """Build client context from tmux environment.

    Returns:
        Dict with pane, session, window, and client from current tmux environment.
        Empty strings if not in tmux.
    """
    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return {"pane": "", "session": "", "window": "", "client": ""}

    # Get pane info (includes session and window_id)
    pane_info = get_pane(pane)
    if not pane_info:
        return {"pane": pane, "session": "", "window": "", "client": ""}

    session = pane_info.session
    window_id = pane_info.window_id  # e.g., "@3"

    # Get client name
    client = get_client_for_pane(pane)

    return {"pane": pane, "session": session, "window": window_id, "client": client}


def validate_pane_id(pane_id: str) -> str | None:
    """Validate pane ID exists.

    Alias for resolution.validate_pane_id for use by server.py.

    Args:
        pane_id: Must be %id format (e.g., "%42")

    Returns:
        pane_id if valid, None if not found or invalid format
    """
    from .resolution import validate_pane_id as _validate

    return _validate(pane_id)


def send_keys(
    pane_id: str,
    *commands,
    enter: bool | None = None,  # Deprecated
    line_ending: LineEnding | str = LineEnding.LF,
    delay: float = 0.05,
    literal: bool = False,
) -> bool:
    """Send keystrokes to a pane.

    Works with any content including interactive commands with Claude.
    Supports control sequences, escape sequences, and text.

    Args:
        pane_id: Target pane ID.
        *commands: One or more commands/keys to send.
        enter: DEPRECATED - use line_ending instead.
        line_ending: How to terminate the command:
            - LineEnding.LF or "lf": Unix line feed (default)
            - LineEnding.CRLF or "crlf": Windows CR+LF
            - LineEnding.CR or "cr": Carriage return only
            - LineEnding.NONE or "": No line ending
        delay: Delay in seconds before sending line ending. Defaults to 0.05.
        literal: If True, send as literal text preserving special characters (;, |, &, etc.).
                 If False (default), interpret tmux key names (C-c, Enter, Up, etc.).

    Returns:
        True if successful.
    """
    if not commands:
        return True

    # Handle deprecated 'enter' parameter
    if enter is not None:
        warnings.warn(
            f"Parameter 'enter' is deprecated. Use 'line_ending' instead.\n"
            f"  Old: send_keys(..., enter={enter})\n"
            f"  New: send_keys(..., line_ending=LineEnding.{'LF' if enter else 'NONE'})",
            DeprecationWarning,
            stacklevel=2,
        )
        line_ending = LineEnding.LF if enter else LineEnding.NONE

    # Send the commands
    args = ["send-keys", "-t", pane_id]

    # Use -l flag for literal mode to preserve special characters
    if literal:
        args.append("-l")

    args.extend(commands)

    code, _, _ = run_tmux(args)
    if code != 0:
        return False

    # Send appropriate line ending
    if line_ending and line_ending != LineEnding.NONE:
        if delay > 0:
            import time

            time.sleep(delay)

        if line_ending == LineEnding.LF or line_ending == "lf":
            code, _, _ = run_tmux(["send-keys", "-t", pane_id, "Enter"])
        elif line_ending == LineEnding.CRLF or line_ending == "crlf":
            # Send Ctrl-M (carriage return) followed by Ctrl-J (line feed)
            code, _, _ = run_tmux(["send-keys", "-t", pane_id, "C-m", "C-j"])
        elif line_ending == LineEnding.CR or line_ending == "cr":
            # Send only Ctrl-M (carriage return)
            code, _, _ = run_tmux(["send-keys", "-t", pane_id, "C-m"])

        return code == 0

    return True


def send_via_paste_buffer(
    pane_id: str,
    content: str,
    enter: bool | None = None,  # Deprecated
    line_ending: LineEnding | str = LineEnding.LF,
    delay: float = 0.05,
) -> bool:
    """Send content using tmux paste buffer for multiline/special content.

    Args:
        pane_id: Target pane ID.
        content: Content to send (can be multiline).
        enter: DEPRECATED - use line_ending instead.
        line_ending: How to terminate the command:
            - LineEnding.LF or "lf": Unix line feed (default)
            - LineEnding.CRLF or "crlf": Windows CR+LF
            - LineEnding.CR or "cr": Carriage return only
            - LineEnding.NONE or "": No line ending
        delay: Delay in seconds before sending line ending.
    """
    if _is_current_pane(pane_id):
        raise CurrentPaneError(f"Cannot send to current pane ({pane_id})")

    # Handle deprecated 'enter' parameter
    if enter is not None:
        warnings.warn(
            f"Parameter 'enter' is deprecated. Use 'line_ending' instead.\n"
            f"  Old: send_via_paste_buffer(..., enter={enter})\n"
            f"  New: send_via_paste_buffer(..., line_ending=LineEnding.{'LF' if enter else 'NONE'})",
            DeprecationWarning,
            stacklevel=2,
        )
        line_ending = LineEnding.LF if enter else LineEnding.NONE

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

    # Send appropriate line ending
    if line_ending and line_ending != LineEnding.NONE:
        if delay > 0:
            import time

            time.sleep(delay)

        if line_ending == LineEnding.LF or line_ending == "lf":
            code, _, _ = run_tmux(["send-keys", "-t", pane_id, "Enter"])
        elif line_ending == LineEnding.CRLF or line_ending == "crlf":
            # Send Ctrl-M (carriage return) followed by Ctrl-J (line feed)
            code, _, _ = run_tmux(["send-keys", "-t", pane_id, "C-m", "C-j"])
        elif line_ending == LineEnding.CR or line_ending == "cr":
            # Send only Ctrl-M (carriage return)
            code, _, _ = run_tmux(["send-keys", "-t", pane_id, "C-m"])

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


def get_pane(pane_id: str) -> PaneInfo | None:
    """Get pane by ID.

    Args:
        pane_id: Tmux pane ID (e.g., '%42').

    Returns:
        PaneInfo or None if not found.
    """
    for pane in list_panes(all=True):
        if pane.pane_id == pane_id:
            return pane
    return None


def get_pane_info(pane_id: str) -> PaneInfo:
    """Get detailed information for a specific pane.

    Deprecated: Use get_pane() instead.

    Args:
        pane_id: Tmux pane ID.

    Returns:
        Complete pane information.

    Raises:
        PaneNotFoundError: If pane doesn't exist.
    """
    pane = get_pane(pane_id)
    if pane is None:
        raise PaneNotFoundError(f"Pane {pane_id} not found")
    return pane


def list_panes(all: bool = True, session: str | None = None, window: str | None = None) -> list[PaneInfo]:
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

    # First run: Get all fields except pane_title as JSON (safe from escaping issues)
    json_format = '{"pane_id":"#{pane_id}","session_name":"#{session_name}","window_id":"#{window_id}","window_index":"#{window_index}","window_name":"#{window_name}","pane_index":"#{pane_index}","pane_pid":"#{pane_pid}","pane_active":"#{pane_active}","pane_current_command":"#{pane_current_command}"}'

    cmd.extend(["-F", json_format])
    code, stdout, _ = run_tmux(cmd)
    if code != 0:
        return []

    # Second run: Get just pane_titles in same order
    title_cmd = ["list-panes"]
    if window:
        title_cmd.extend(["-t", window])
    elif session:
        title_cmd.extend(["-t", session])
    elif all:
        title_cmd.append("-a")

    title_cmd.extend(["-F", "#{pane_title}"])
    _, title_stdout, _ = run_tmux(title_cmd)

    titles = title_stdout.strip().split("\n")
    panes = []
    current_pane_id = _get_current_pane()

    for i, line in enumerate(stdout.strip().split("\n")):
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
                    window_id=data["window_id"],
                    window_index=window_idx,
                    window_name=data["window_name"] or str(window_idx),
                    pane_index=pane_idx,
                    pane_title=titles[i] if i < len(titles) else "",  # Get title by index
                    pane_pid=int(data["pane_pid"]),
                    pane_current_command=data.get("pane_current_command", ""),
                    is_active=data["pane_active"] == "1",
                    is_current=data["pane_id"] == current_pane_id,
                    swp=f"{data['session_name']}:{window_idx}.{pane_idx}",
                )
            )
        except (json.JSONDecodeError, KeyError, ValueError, IndexError):
            continue

    panes.sort(key=lambda p: (p.session, p.window_index, p.pane_index))
    return panes


def get_client_for_pane(pane_id: str) -> str:
    """Get client name for a specific pane.

    Args:
        pane_id: Pane ID (e.g. '%42').

    Returns:
        Client name (e.g. '/dev/pts/3') or empty string if not found.
    """
    json_format = '{"pane_id":"#{pane_id}","client_name":"#{client_name}"}'
    cmd = ["list-clients", "-F", json_format]
    code, stdout, _ = run_tmux(cmd)

    if code != 0:
        return ""

    for line in stdout.strip().split("\n"):
        if not line:
            continue
        try:
            data = json.loads(line)
            if data["pane_id"] == pane_id:
                return data["client_name"]
        except (json.JSONDecodeError, KeyError):
            continue

    return ""


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


def capture_pane(pane_id: str) -> str:
    """Capture all pane content (history + visible screen).

    Always uses -S - to capture everything. Works correctly for:
    - Fresh panes with no history (captures visible screen)
    - Panes with history (captures history + visible screen)

    Filtering and pagination should be done in Python, not via tmux flags.

    Args:
        pane_id: Tmux pane ID (%format).

    Returns:
        All pane content with trailing empty lines stripped.
    """
    code, stdout, _ = run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", "-"])
    return __strip_trailing_empty_lines(stdout) if code == 0 else ""


def create_panes_with_layout(session: str, num_panes: int, layout: str = "even-horizontal") -> list[str]:
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
