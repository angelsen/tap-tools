"""Internal streaming output from tmux panes.

All classes and functions in this module are internal to the tmux package.
Multiple Stream instances can coexist safely.
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Optional

from .core import run_tmux


class _Stream:
    """Internal stream handler for tmux pane output.

    Handles streaming output from tmux panes with position tracking.
    Multiple instances can coexist safely.

    Attributes:
        pane_id: Tmux pane ID.
        session_window_pane: Session:window.pane format.
        stream_dir: Directory for stream files.
        stream_file: Path to stream content file.
        metadata_file: Path to metadata file.
    """

    def __init__(self, pane_id: str, session_window_pane: str, stream_dir: Optional[Path] = None):
        self.pane_id = pane_id
        self.session_window_pane = session_window_pane
        self.stream_dir = stream_dir or Path("/tmp/termtap/streams")
        self.stream_file = self.stream_dir / f"{pane_id}.stream"
        self.metadata_file = self.stream_dir / f"{pane_id}.json"

    def _ensure_sync(self) -> bool:
        """Ensure files are in sync.

        Returns:
            True if ready, False if cleaned up.
        """
        stream_exists = self.stream_file.exists()
        metadata_exists = self.metadata_file.exists()

        if not stream_exists and not metadata_exists:
            return True
        if stream_exists != metadata_exists:
            if stream_exists:
                self.stream_file.unlink()
            if metadata_exists:
                self.metadata_file.unlink()
            return False

        # Both exist - verify inode
        metadata = self._read_metadata_unsafe()
        stored_inode = metadata.get("stream_inode")
        current_inode = self._get_stream_file_inode()

        if stored_inode != current_inode:
            self.stream_file.unlink()
            self.metadata_file.unlink()
            return False

        return True

    def _get_stream_file_inode(self) -> Optional[int]:
        """Get inode of stream file if it exists."""
        try:
            return self.stream_file.stat().st_ino
        except (OSError, FileNotFoundError):
            return None

    def _read_metadata_unsafe(self) -> dict:
        """Read metadata without sync check."""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _write_metadata_unsafe(self, metadata: dict) -> None:
        """Write metadata without sync check."""
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def _get_file_position(self) -> int:
        """Get current position in stream file."""
        if not self.stream_file.exists():
            return 0
        return self.stream_file.stat().st_size

    def start(self) -> bool:
        """Ensure streaming is active.

        Reuses existing pipe if valid, creates new one otherwise.

        Returns:
            True if streaming started successfully.
        """
        self._ensure_sync()

        code, out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        if code == 0 and out.strip() == "1":
            cmd_code, cmd_out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_command}"])
            if cmd_code == 0 and str(self.stream_file) in cmd_out:
                if self.stream_file.exists() and self.metadata_file.exists():
                    metadata = self._read_metadata_unsafe()
                    if metadata.get("stream_inode") == self._get_stream_file_inode():
                        return True

                self.cleanup()

        self.stream_dir.mkdir(parents=True, exist_ok=True)
        self.stream_file.touch()

        metadata = {
            "pane_id": self.pane_id,
            "session_window_pane": self.session_window_pane,
            "stream_inode": self._get_stream_file_inode(),
            "created": time.time(),
            "commands": {},
            "positions": {"bash_last": 0},
        }
        self._write_metadata_unsafe(metadata)

        code, out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        if code == 0 and out.strip() == "1":
            return True

        # Escape % characters for tmux
        escaped_path = str(self.stream_file).replace("%", "%%")
        code, _, _ = run_tmux(["pipe-pane", "-t", self.pane_id, f"cat >> {escaped_path}"])

        if code != 0:
            self.cleanup()
            return False

        return True

    def stop(self) -> bool:
        """Stop streaming from pane.

        Returns:
            True if successful.
        """
        code, _, _ = run_tmux(["pipe-pane", "-t", self.pane_id])
        return code == 0

    def cleanup(self):
        """Delete both stream and metadata files."""
        if self.stream_file.exists():
            self.stream_file.unlink()
        if self.metadata_file.exists():
            self.metadata_file.unlink()

    def is_running(self) -> bool:
        """Check if any pipe is active for this pane."""
        code, out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        return code == 0 and out.strip() == "1"

    def is_active(self) -> bool:
        """Check if we have valid tracking files."""
        return self._ensure_sync() and self.stream_file.exists()

    def _read_stream_slice(self, start: int, length: int) -> bytes:
        """Read raw bytes from stream file."""
        if not self.stream_file.exists() or length <= 0:
            return b""

        with open(self.stream_file, "rb") as f:
            f.seek(start)
            return f.read(length)

    def _render_stream_slice(self, start: int, length: int) -> str:
        """Render content with ANSI processing via temporary tmux window."""
        if length <= 0:
            return ""

        session = self.session_window_pane.split(":")[0]

        # Generate unique window name
        content_hash = hashlib.md5(f"{self.pane_id}:{start}:{length}".encode()).hexdigest()[:8]
        window_name = f"tt_render_{content_hash}"

        # Tail uses 1-based byte positions
        cmd = f"tail -c +{start + 1} '{self.stream_file}' | head -c {length} && sleep 0.2"

        code, _, _ = run_tmux(["new-window", "-t", session, "-d", "-n", window_name, "sh", "-c", cmd])

        if code != 0:
            content = self._read_stream_slice(start, length)
            return content.decode("utf-8", errors="replace")

        time.sleep(0.1)

        code, output, _ = run_tmux(["capture-pane", "-t", f"{session}:{window_name}", "-p", "-S", "-", "-E", "-"])

        run_tmux(["kill-window", "-t", f"{session}:{window_name}"])

        if code == 0 and output:
            # Remove trailing empty lines from tmux output
            lines = output.rstrip("\n").split("\n")
            while lines and not lines[-1].strip():
                lines.pop()
            return "\n".join(lines) + "\n" if lines else ""

        content = self._read_stream_slice(start, length)
        return content.decode("utf-8", errors="replace")

    def mark_command(self, cmd_id: str, command: str) -> str:
        """Mark command start position.

        Args:
            cmd_id: Command identifier.
            command: Command string being executed.

        Returns:
            Command ID for retrieving output later.
        """
        if not self._ensure_sync():
            if not self.start():
                return cmd_id

        metadata = self._read_metadata_unsafe()

        # Initialize structure if missing
        if "commands" not in metadata:
            metadata["commands"] = {}
        if "positions" not in metadata:
            metadata["positions"] = {"bash_last": 0}

        position = self._get_file_position()
        metadata["commands"][cmd_id] = {"position": position, "command": command, "time": time.time()}
        metadata["positions"]["bash_last"] = position
        self._write_metadata_unsafe(metadata)

        return cmd_id

    def mark_command_end(self, cmd_id: str) -> None:
        """Mark command end position."""
        if not self._ensure_sync():
            return

        metadata = self._read_metadata_unsafe()
        if "commands" in metadata and cmd_id in metadata["commands"]:
            end_pos = self._get_file_position()
            metadata["commands"][cmd_id]["end_position"] = end_pos
            metadata["positions"]["bash_last"] = end_pos
            self._write_metadata_unsafe(metadata)

    def read_command_output(self, cmd_id: str, as_displayed: bool = False) -> str:
        """Read output for a specific command."""
        if not self._ensure_sync():
            return ""

        metadata = self._read_metadata_unsafe()
        cmd_info = metadata.get("commands", {}).get(cmd_id)

        if not cmd_info:
            return ""

        start = cmd_info["position"]
        end = cmd_info.get("end_position", self._get_file_position())
        length = end - start

        if length <= 0:
            return ""

        if as_displayed:
            return self._render_stream_slice(start, length)
        else:
            content = self._read_stream_slice(start, length)
            return content.decode("utf-8", errors="replace")

    def read_all(self, as_displayed: bool = False) -> str:
        """Read entire stream content."""
        if not self._ensure_sync():
            return ""

        if not self.stream_file.exists():
            return ""

        length = self._get_file_position()
        if length <= 0:
            return ""

        if as_displayed:
            return self._render_stream_slice(0, length)
        else:
            content = self._read_stream_slice(0, length)
            return content.decode("utf-8", errors="replace")

    def read_last_lines(self, lines: int, as_displayed: bool = False) -> str:
        """Read last N lines from stream."""
        if not self._ensure_sync():
            return ""

        # Line-based reading requires full content first
        content = self.read_all(as_displayed=False)
        if not content:
            return ""

        lines_list = content.splitlines()
        if len(lines_list) <= lines:
            if as_displayed:
                return self.read_all(as_displayed=True)
            else:
                return content

        # Locate start of last N lines
        last_lines = lines_list[-lines:]
        last_content = "\n".join(last_lines)

        if as_displayed:
            # Calculate byte position for display rendering
            prefix = "\n".join(lines_list[:-lines])
            start_pos = len(prefix.encode("utf-8")) + (1 if prefix else 0)
            length = len(content.encode("utf-8")) - start_pos
            return self._render_stream_slice(start_pos, length)
        else:
            return last_content

    def capture_full_buffer(self, pane_id: str) -> str:
        """Capture entire pane content including scrollback.

        Args:
            pane_id: The tmux pane ID to capture from.

        Returns:
            Complete pane content with scrollback.
        """
        code, output, _ = run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", "-", "-E", "-"])
        return output if code == 0 else ""
