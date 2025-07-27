"""Tmux streaming operations - pane-first architecture.

Sidecar files are the source of truth. No in-memory state.
Each pane has one stream file and one metadata file.
"""

import time
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from ..types import SessionWindowPane
from .utils import _run_tmux


class _StreamHandle:
    """Handle for a tmux pane stream - stateless, file-based.
    
    All state is read from/written to sidecar files immediately.
    No in-memory caching of metadata.
    
    Attributes:
        pane_id: Pane identifier string (e.g., "%42").
        session_window_pane: Full identifier (e.g., "epic-swan:0.0").
        stream_dir: Directory for stream files.
        stream_file: Path to stream output file.
        metadata_file: Path to metadata file.
    """

    def __init__(self, pane_id: str, session_window_pane: SessionWindowPane, stream_dir: Optional[Path] = None):
        self.pane_id = pane_id
        self.session_window_pane = session_window_pane
        self.stream_dir = stream_dir or Path("/tmp/termtap/streams")
        self.stream_dir.mkdir(parents=True, exist_ok=True)

        safe_id = pane_id.replace(":", "_").replace("%", "")
        self.stream_file = self.stream_dir / f"{safe_id}.stream"
        self.metadata_file = self.stream_dir / f"{safe_id}.meta.json"

    def _read_metadata(self) -> dict:
        """Read metadata from file. Returns empty dict if not exists."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Return default structure
        return {
            "pane_id": self.pane_id,
            "session_window_pane": self.session_window_pane,
            "stream_started": datetime.now().isoformat(),
            "bash_marks": {},
            "last_read": 0,
            "read_bookmarks": {},
            "last_activity": None
        }
    
    def _write_metadata(self, metadata: dict) -> None:
        """Write metadata to file."""
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def start(self) -> bool:
        """Start streaming from pane to file."""
        code, out, _ = _run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        if code == 0 and out.strip() == "1":
            return True

        shell_cmd = f"cat >> {self.stream_file}"
        code, _, _ = _run_tmux(["pipe-pane", "-o", "-t", self.pane_id, shell_cmd])
        return code == 0

    def stop(self) -> bool:
        """Stop streaming from pane."""
        code, _, _ = _run_tmux(["pipe-pane", "-t", self.pane_id])
        return code == 0

    def is_running(self) -> bool:
        """Check if streaming is active."""
        code, out, _ = _run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        return code == 0 and out.strip() == "1"

    def _get_file_position(self) -> int:
        """Get current position in stream file."""
        return self.stream_file.stat().st_size if self.stream_file.exists() else 0

    def mark_command(self, cmd_id: str, command: str) -> None:
        """Mark position for a bash command."""
        metadata = self._read_metadata()
        pos = self._get_file_position()
        
        metadata["bash_marks"][cmd_id] = {
            "position": pos,
            "time": datetime.now().isoformat(),
            "command": command
        }
        metadata["last_activity"] = datetime.now().isoformat()
        
        self._write_metadata(metadata)

    def mark_read(self, mark_name: str = "last_read") -> None:
        """Mark position for a read operation."""
        metadata = self._read_metadata()
        pos = self._get_file_position()
        
        if mark_name == "last_read":
            metadata["last_read"] = pos
        else:
            metadata["read_bookmarks"][mark_name] = pos
        
        metadata["last_activity"] = datetime.now().isoformat()
        self._write_metadata(metadata)

    def read_from_mark(self, cmd_id: str) -> str:
        """Read output from a specific command mark."""
        metadata = self._read_metadata()
        mark = metadata["bash_marks"].get(cmd_id)
        
        if not mark:
            return ""
        
        return self._read_from_position(mark["position"])

    def read_since_last(self) -> str:
        """Read new content since last read() call."""
        metadata = self._read_metadata()
        last_pos = metadata.get("last_read", 0)
        return self._read_from_position(last_pos)

    def read_all(self) -> str:
        """Read entire stream file."""
        return self._read_from_position(0)

    def read_last_lines(self, lines: int) -> str:
        """Read last N lines from stream."""
        if not self.stream_file.exists():
            return ""
        
        # Simple implementation - can be optimized later
        content = self.read_all()
        lines_list = content.splitlines()
        if len(lines_list) <= lines:
            return content
        return '\n'.join(lines_list[-lines:])

    def read_between_commands(self, start_cmd: str, end_cmd: str) -> str:
        """Read output between two command marks."""
        metadata = self._read_metadata()
        start_mark = metadata["bash_marks"].get(start_cmd)
        end_mark = metadata["bash_marks"].get(end_cmd)
        
        if not start_mark or not end_mark:
            return ""
        
        start_pos = start_mark["position"]
        end_pos = end_mark["position"]
        
        if not self.stream_file.exists() or end_pos <= start_pos:
            return ""
        
        with open(self.stream_file, "rb") as f:
            f.seek(start_pos)
            content = f.read(end_pos - start_pos)
        
        return content.decode("utf-8", errors="replace")

    def _read_from_position(self, position: int) -> str:
        """Read from specific position to end of file."""
        if not self.stream_file.exists():
            return ""
        
        with open(self.stream_file, "rb") as f:
            f.seek(position)
            content = f.read()
        
        return content.decode("utf-8", errors="replace")

    def clear(self):
        """Clear stream file and metadata (useful for testing)."""
        if self.stream_file.exists():
            self.stream_file.unlink()
        if self.metadata_file.exists():
            self.metadata_file.unlink()


class _StreamManager:
    """Manages streams for all panes - stateless.
    
    Attributes:
        stream_dir: Directory for stream files.
        streams: Dict mapping pane IDs to stream handles (lightweight).
    """

    def __init__(self, stream_dir: Optional[Path] = None):
        self.stream_dir = stream_dir or Path("/tmp/termtap/streams")
        self.streams: Dict[str, _StreamHandle] = {}

    def get_stream(self, pane_id: str, session_window_pane: SessionWindowPane) -> _StreamHandle:
        """Get or create stream for pane."""
        if pane_id not in self.streams:
            self.streams[pane_id] = _StreamHandle(pane_id, session_window_pane, self.stream_dir)
        return self.streams[pane_id]

    def get_stream_if_exists(self, pane_id: str) -> _StreamHandle | None:
        """Get stream only if it already exists in our map."""
        return self.streams.get(pane_id)

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
                
        for meta_file in self.stream_dir.glob("*.meta.json"):
            if meta_file.stat().st_mtime < cutoff_time:
                meta_file.unlink()