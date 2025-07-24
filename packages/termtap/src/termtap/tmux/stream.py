"""Internal tmux streaming operations.

This module provides internal utilities for streaming tmux pane output
to files for monitoring and tracking command execution. All classes and
functions in this module are internal and should not be used directly.
"""

import time
from pathlib import Path
from typing import Dict, Tuple
import uuid

from .utils import _run_tmux


class _StreamHandle:
    """Handle for a tmux pane stream."""

    def __init__(self, pane_id: str, stream_dir: Path = None):
        self.pane_id = pane_id
        self.stream_dir = stream_dir or Path("/tmp/termtap/streams")
        self.stream_dir.mkdir(parents=True, exist_ok=True)

        safe_id = pane_id.replace(":", "_").replace("%", "")
        self.stream_file = self.stream_dir / f"{safe_id}.stream"
        self.positions_file = self.stream_dir / f"{safe_id}.positions"

        self.positions: Dict[str, int] = {}
        if self.positions_file.exists():
            try:
                import json

                with open(self.positions_file, "r") as f:
                    self.positions = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    def start(self) -> bool:
        """Start streaming from pane to file."""
        code, out, _ = _run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        if code == 0 and out.strip() == "1":
            return True

        # Start piping to our stream file
        # Note: shell command must be a single argument
        # Use -o flag to only open if not already piping
        shell_cmd = f"cat >> {self.stream_file}"
        code, _, _ = _run_tmux(["pipe-pane", "-o", "-t", self.pane_id, shell_cmd])
        return code == 0

    def stop(self) -> bool:
        """Stop streaming from pane."""
        code, _, _ = _run_tmux(["pipe-pane", "-t", self.pane_id])
        return code == 0

    def mark_position(self, cmd_id: str) -> int:
        """Mark current position in stream for a command."""
        pos = self.stream_file.stat().st_size if self.stream_file.exists() else 0
        self.positions[cmd_id] = pos

        # Save to sidecar file with indent for debuggability
        import json

        with open(self.positions_file, "w") as f:
            json.dump(self.positions, f, indent=2)

        return pos

    def read_from(self, cmd_id: str) -> str:
        """Read stream content from a command's position."""
        if cmd_id not in self.positions:
            return ""

        start_pos = self.positions[cmd_id]

        if not self.stream_file.exists():
            return ""

        with open(self.stream_file, "rb") as f:
            f.seek(start_pos)
            content = f.read()

        return content.decode("utf-8", errors="replace")

    def read_new(self, last_pos: int) -> Tuple[str, int]:
        """Read new content since last_pos, return (content, new_pos)."""
        if not self.stream_file.exists():
            return "", last_pos

        current_size = self.stream_file.stat().st_size
        if current_size <= last_pos:
            return "", last_pos

        with open(self.stream_file, "rb") as f:
            f.seek(last_pos)
            content = f.read()

        return content.decode("utf-8", errors="replace"), current_size

    def clear(self):
        """Clear stream file (useful for testing)."""
        if self.stream_file.exists():
            self.stream_file.unlink()
        self.positions.clear()


class _StreamManager:
    """Manages streams for all panes."""

    def __init__(self, stream_dir: Path = None):
        self.stream_dir = stream_dir or Path("/tmp/termtap/streams")
        self.streams: Dict[str, _StreamHandle] = {}

    def get_stream(self, pane_id: str) -> _StreamHandle:
        """Get or create stream for pane."""
        if pane_id not in self.streams:
            self.streams[pane_id] = _StreamHandle(pane_id, self.stream_dir)
            self.streams[pane_id].start()
        return self.streams[pane_id]

    def stop_all(self):
        """Stop all active streams."""
        for stream in self.streams.values():
            stream.stop()

    def cleanup_old_streams(self, max_age_hours: int = 24):
        """Remove old stream files."""
        if not self.stream_dir.exists():
            return

        cutoff_time = time.time() - (max_age_hours * 3600)

        for stream_file in self.stream_dir.glob("*.stream"):
            if stream_file.stat().st_mtime < cutoff_time:
                stream_file.unlink()


def _get_pane_for_session(session: str) -> str:
    """Get the first pane for a session in format suitable for -t flag."""
    return f"{session}:0.0"


def _send_command(pane_id: str, command: str) -> str:
    """Send command and return command ID for tracking."""
    from ..tmux import send_keys

    cmd_id = str(uuid.uuid4())[:8]
    send_keys(pane_id, command)
    return cmd_id
