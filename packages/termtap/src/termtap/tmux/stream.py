"""Streaming output from tmux panes with guaranteed sync."""

import json
import time
from pathlib import Path
from typing import Optional

from .core import run_tmux


class Stream:
    """Stream handler with guaranteed sync between stream and metadata files.

    Core principle: Both files exist and are valid, or neither exists.
    Any inconsistency triggers deletion of both files.
    """

    def __init__(self, pane_id: str, session_window_pane: str, stream_dir: Path):
        self.pane_id = pane_id
        self.session_window_pane = session_window_pane
        self.stream_dir = stream_dir
        self.stream_file = stream_dir / f"{pane_id}.stream"
        self.metadata_file = stream_dir / f"{pane_id}.json"

    def _ensure_sync(self) -> bool:
        """Ensure files are in sync. Returns True if ready, False if cleaned up."""
        stream_exists = self.stream_file.exists()
        metadata_exists = self.metadata_file.exists()

        # Both missing - clean state
        if not stream_exists and not metadata_exists:
            return True

        # One missing - delete the other
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
            # Inode mismatch - files out of sync
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
        """Read metadata without sync check (internal use only)."""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _write_metadata_unsafe(self, metadata: dict) -> None:
        """Write metadata without sync check (internal use only)."""
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def _get_file_position(self) -> int:
        """Get current position in stream file."""
        if not self.stream_file.exists():
            return 0
        return self.stream_file.stat().st_size

    def start(self) -> bool:
        """Start streaming - creates both files atomically."""
        # Always ensure sync first
        self._ensure_sync()

        # Check if already piping
        code, out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        if code == 0 and out.strip() == "1":
            # Already piping - verify it's ours
            cmd_code, cmd_out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_command}"])
            if cmd_code == 0 and str(self.stream_file) in cmd_out:
                return True

        # Create both files together
        self.stream_dir.mkdir(parents=True, exist_ok=True)
        self.stream_file.touch()

        # Write metadata with current inode
        metadata = {
            "pane_id": self.pane_id,
            "session_window_pane": self.session_window_pane,
            "stream_inode": self._get_stream_file_inode(),
            "created": time.time(),
            "commands": {},
            "positions": {"bash_last": 0, "user_last": 0},
        }
        self._write_metadata_unsafe(metadata)

        # Start piping - escape % as %% (tmux interprets %xxx as format specifiers)
        escaped_path = str(self.stream_file).replace("%", "%%")
        code, _, _ = run_tmux(["pipe-pane", "-t", self.pane_id, f"cat >> {escaped_path}"])

        if code != 0:
            # Failed - clean up both files
            self.cleanup()
            return False

        return True

    def stop(self) -> bool:
        """Stop streaming from pane."""
        code, _, _ = run_tmux(["pipe-pane", "-t", self.pane_id])
        return code == 0

    def cleanup(self):
        """Delete both files."""
        if self.stream_file.exists():
            self.stream_file.unlink()
        if self.metadata_file.exists():
            self.metadata_file.unlink()

    def is_running(self) -> bool:
        """Check if streaming is active."""
        code, out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        return code == 0 and out.strip() == "1"

    def is_active(self) -> bool:
        """Check if stream files exist and are in sync."""
        return self._ensure_sync() and self.stream_file.exists()

    # Command tracking

    def mark_command(self, cmd_id: str, command: str) -> None:
        """Mark command position - ensures sync first."""
        if not self._ensure_sync():
            # Files were cleaned, start fresh
            if not self.start():
                return

        metadata = self._read_metadata_unsafe()

        # Ensure structure exists (defensive against corruption)
        if "commands" not in metadata:
            metadata["commands"] = {}
        if "positions" not in metadata:
            metadata["positions"] = {"bash_last": 0, "user_last": 0}

        position = self._get_file_position()
        metadata["commands"][cmd_id] = {"position": position, "command": command, "time": time.time()}
        metadata["positions"]["bash_last"] = position
        self._write_metadata_unsafe(metadata)

    def mark_command_end(self, cmd_id: str) -> None:
        """Mark end position for a command."""
        if not self._ensure_sync():
            return

        metadata = self._read_metadata_unsafe()
        if "commands" in metadata and cmd_id in metadata["commands"]:
            end_pos = self._get_file_position()
            metadata["commands"][cmd_id]["end_position"] = end_pos
            metadata["positions"]["bash_last"] = end_pos
            self._write_metadata_unsafe(metadata)

    def mark_user_read(self) -> None:
        """Mark position for user read() operation."""
        if not self._ensure_sync():
            return

        metadata = self._read_metadata_unsafe()
        if "positions" not in metadata:
            metadata["positions"] = {"bash_last": 0, "user_last": 0}
        metadata["positions"]["user_last"] = self._get_file_position()
        self._write_metadata_unsafe(metadata)

    # Reading operations

    def read_command_output(self, cmd_id: str) -> str:
        """Read output for a specific command."""
        if not self._ensure_sync():
            return ""

        metadata = self._read_metadata_unsafe()
        cmd_info = metadata.get("commands", {}).get(cmd_id)

        if not cmd_info:
            return ""

        # Read from stream file
        start = cmd_info["position"]
        end = cmd_info.get("end_position", self._get_file_position())

        if end <= start:
            return ""

        with open(self.stream_file, "rb") as f:
            f.seek(start)
            content = f.read(end - start)

        return content.decode("utf-8", errors="replace")

    def read_since_user_last(self) -> str:
        """Read new content since last user read."""
        if not self._ensure_sync():
            return ""

        metadata = self._read_metadata_unsafe()
        last_pos = metadata.get("positions", {}).get("user_last", 0)
        current_pos = self._get_file_position()

        if current_pos <= last_pos:
            return ""

        with open(self.stream_file, "rb") as f:
            f.seek(last_pos)
            content = f.read(current_pos - last_pos)

        return content.decode("utf-8", errors="replace")

    def read_all(self) -> str:
        """Read entire stream content."""
        if not self._ensure_sync():
            return ""

        if not self.stream_file.exists():
            return ""

        with open(self.stream_file, "rb") as f:
            content = f.read()

        return content.decode("utf-8", errors="replace")

    def read_last_lines(self, lines: int) -> str:
        """Read last N lines from stream."""
        if not self._ensure_sync():
            return ""

        content = self.read_all()
        if not content:
            return ""

        lines_list = content.splitlines()
        if len(lines_list) <= lines:
            return content

        return "\n".join(lines_list[-lines:])


class StreamManager:
    """Manages streams for all panes."""

    def __init__(self, stream_dir: Optional[Path] = None):
        self.stream_dir = stream_dir or Path("/tmp/termtap/streams")
        self.streams: dict[str, Stream] = {}

    def get_stream(self, pane_id: str, session_window_pane: str) -> Stream:
        """Get or create stream for pane."""
        if pane_id not in self.streams:
            self.streams[pane_id] = Stream(pane_id, session_window_pane, self.stream_dir)
        return self.streams[pane_id]

    def cleanup_all(self):
        """Clean up all streams."""
        for stream in self.streams.values():
            stream.cleanup()
        self.streams.clear()
