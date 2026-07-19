"""Pane operations - all pane-related functionality.

PUBLIC API:
  - PaneInfo: Complete pane information data class
  - list_panes: List all panes with full information
  - get_pane: Get single pane by ID
  - get_client_for_pane: Get client name for a pane
  - send_keys: Send keystrokes to pane
  - paste_text: Paste text into pane via buffer (for commands)
  - capture_pane: Capture all pane content (history + visible)
  - build_client_context: Build client context from tmux environment
"""

from dataclasses import dataclass
import json
import os
import re

from .core import run_tmux
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
        pane_index: Pane index.
        pane_pid: Process ID of pane.
        pane_current_command: Current process name (e.g., 'bash', 'python').
        swp: Session:window.pane format.
    """

    pane_id: str  # %42
    session: str
    window_id: str  # @3
    window_index: int
    pane_index: int
    pane_pid: int
    pane_current_command: str
    swp: SessionWindowPane  # session:window.pane


# Shared by list_panes/get_pane. JSON keeps field parsing safe from
# escaping issues; pane_title is deliberately absent (it can hold quotes).
_PANE_FORMAT = (
    '{"pane_id":"#{pane_id}","session_name":"#{session_name}","window_id":"#{window_id}",'
    '"window_index":"#{window_index}","pane_index":"#{pane_index}","pane_pid":"#{pane_pid}",'
    '"pane_current_command":"#{pane_current_command}"}'
)


def _parse_pane(line: str) -> PaneInfo | None:
    """Parse one _PANE_FORMAT JSON line into PaneInfo."""
    try:
        data = json.loads(line)
        window_idx = int(data["window_index"])
        pane_idx = int(data["pane_index"])
        return PaneInfo(
            pane_id=data["pane_id"],
            session=data["session_name"],
            window_id=data["window_id"],
            window_index=window_idx,
            pane_index=pane_idx,
            pane_pid=int(data["pane_pid"]),
            pane_current_command=data.get("pane_current_command", ""),
            swp=f"{data['session_name']}:{window_idx}.{pane_idx}",
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


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


def send_keys(
    pane_id: str,
    *commands,
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


def paste_text(pane_id: str, text: str, delay: float = 0.05) -> bool:
    """Paste text into a pane via tmux paste-buffer, then send Enter.

    Preferred over send_keys for command strings: send-keys types
    character-by-character, which triggers per-keystroke processing in
    shells (fish autosuggestion/highlighting redraws leave artifacts in
    the stream buffer). paste-buffer -p uses bracketed paste when the
    application requested it and falls back to a plain paste otherwise.

    Args:
        pane_id: Target pane ID.
        text: Text to paste (single or multi-line).
        delay: Delay in seconds between paste and Enter.

    Returns:
        True if successful.
    """
    code, _, _ = run_tmux(["load-buffer", "-b", "termtap_send", "-"], input=text)
    if code != 0:
        return False

    code, _, _ = run_tmux(["paste-buffer", "-t", pane_id, "-b", "termtap_send", "-d", "-p"])
    if code != 0:
        return False

    if delay > 0:
        import time

        time.sleep(delay)

    code, _, _ = run_tmux(["send-keys", "-t", pane_id, "Enter"])
    return code == 0


def get_pane(pane_id: str) -> PaneInfo | None:
    """Get pane by ID with a single targeted tmux call.

    On the hot path (Pane.capture_*, current_process TTL refresh) — must
    not enumerate every pane in the server.

    Args:
        pane_id: Tmux pane ID (e.g., '%42').

    Returns:
        PaneInfo or None if not found.
    """
    code, stdout, _ = run_tmux(["display-message", "-p", "-t", pane_id, _PANE_FORMAT])
    if code != 0:
        return None
    return _parse_pane(stdout.strip())


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

    cmd.extend(["-F", _PANE_FORMAT])
    code, stdout, _ = run_tmux(cmd)
    if code != 0:
        return []

    panes = [info for line in stdout.strip().split("\n") if line and (info := _parse_pane(line))]
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


# Strip escape sequences that some terminal emulators leak into tmux pane buffer
# OSC: \033]...\007 or \033]...\033\\  (e.g., title setting — confirmed on Alacritty)
#      Unterminated OSC is stripped to end of line/string — otherwise the Fe
#      branch would eat only \033] and leak the payload as matchable text.
# CSI: \033[...X                       (e.g., colors, cursor — defensive)
# Fe:  \033X                           (e.g., charset switching — defensive)
_ESCAPE_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b\n]*(?:\x07|\x1b\\|(?=\n)|$)|[@-Z\\-_])")


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
    if code != 0:
        return ""
    cleaned = _ESCAPE_RE.sub("", stdout)
    return __strip_trailing_empty_lines(cleaned)
