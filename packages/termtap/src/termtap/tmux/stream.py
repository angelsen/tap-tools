"""Streaming output from tmux panes - no global state, multiple instances can coexist."""

import json
import time
import hashlib
from pathlib import Path
from typing import Optional

from .core import run_tmux


class Stream:
    """Stream handler for tmux pane output.
    
    Key principles:
    - No ownership concept - tmux owns the pipe, we just track positions
    - Multiple Stream instances can share the same files
    - Metadata and stream files must stay in sync (inode tracking)
    - No global StreamManager needed
    """
    
    def __init__(self, pane_id: str, session_window_pane: str, stream_dir: Path = None):
        self.pane_id = pane_id
        self.session_window_pane = session_window_pane
        self.stream_dir = stream_dir or Path("/tmp/termtap/streams")
        self.stream_file = self.stream_dir / f"{pane_id}.stream"
        self.metadata_file = self.stream_dir / f"{pane_id}.json"
    
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
        """Ensure streaming is active - reuses existing pipe if valid."""
        # Always ensure sync first
        self._ensure_sync()
        
        # Check if already piping
        code, out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        if code == 0 and out.strip() == "1":
            # Someone is piping - check where
            cmd_code, cmd_out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_command}"])
            if cmd_code == 0 and str(self.stream_file) in cmd_out:
                # Already piping to our file
                if self.stream_file.exists() and self.metadata_file.exists():
                    # Verify sync
                    metadata = self._read_metadata_unsafe()
                    if metadata.get("stream_inode") == self._get_stream_file_inode():
                        return True  # All good, reuse existing pipe
                
                # Files missing or out of sync - clean up and start fresh
                self.cleanup()
        
        # Create directory and files
        self.stream_dir.mkdir(parents=True, exist_ok=True)
        self.stream_file.touch()
        
        # Initialize metadata
        metadata = {
            "pane_id": self.pane_id,
            "session_window_pane": self.session_window_pane,
            "stream_inode": self._get_stream_file_inode(),
            "created": time.time(),
            "commands": {},
            "positions": {"bash_last": 0, "user_last": 0},
        }
        self._write_metadata_unsafe(metadata)
        
        # Check again if someone started piping while we were setting up
        code, out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        if code == 0 and out.strip() == "1":
            # Someone else started - that's fine, we have our tracking files
            return True
        
        # Start piping - escape % as %%
        escaped_path = str(self.stream_file).replace("%", "%%")
        code, _, _ = run_tmux(["pipe-pane", "-t", self.pane_id, f"cat >> {escaped_path}"])
        
        if code != 0:
            # Failed - clean up
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
        """Check if any pipe is active for this pane."""
        code, out, _ = run_tmux(["display", "-t", self.pane_id, "-p", "#{pane_pipe}"])
        return code == 0 and out.strip() == "1"
    
    def is_active(self) -> bool:
        """Check if we have valid tracking files."""
        return self._ensure_sync() and self.stream_file.exists()
    
    # Reading utilities
    
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
            
        # Get session from pane's session:window.pane format
        session = self.session_window_pane.split(":")[0]
        
        # Generate unique window name
        content_hash = hashlib.md5(f"{self.pane_id}:{start}:{length}".encode()).hexdigest()[:8]
        window_name = f"tt_render_{content_hash}"
        
        # Build command to extract and display the slice
        # Note: tail uses 1-based byte positions, so we add 1
        cmd = f"tail -c +{start + 1} '{self.stream_file}' | head -c {length} && sleep 0.2"
        
        # Create temporary window
        code, _, _ = run_tmux(["new-window", "-t", session, "-d", "-n", window_name, "sh", "-c", cmd])
        
        if code != 0:
            # Fallback to raw content
            content = self._read_stream_slice(start, length)
            return content.decode("utf-8", errors="replace")
        
        # Give time for content to render
        time.sleep(0.1)
        
        # Capture the rendered output
        code, output, _ = run_tmux(["capture-pane", "-t", f"{session}:{window_name}", "-p"])
        
        # Clean up window
        run_tmux(["kill-window", "-t", f"{session}:{window_name}"])
        
        if code == 0 and output:
            # Strip trailing empty lines that tmux adds
            lines = output.rstrip("\n").split("\n")
            while lines and not lines[-1].strip():
                lines.pop()
            return "\n".join(lines) + "\n" if lines else ""
        
        # Fallback to raw content
        content = self._read_stream_slice(start, length)
        return content.decode("utf-8", errors="replace")
    
    # Command tracking
    
    def mark_command(self, cmd_id: str, command: str) -> None:
        """Mark command start position."""
        if not self._ensure_sync():
            # Files were cleaned, start fresh
            if not self.start():
                return
        
        metadata = self._read_metadata_unsafe()
        
        # Ensure structure exists
        if "commands" not in metadata:
            metadata["commands"] = {}
        if "positions" not in metadata:
            metadata["positions"] = {"bash_last": 0, "user_last": 0}
        
        position = self._get_file_position()
        metadata["commands"][cmd_id] = {
            "position": position,
            "command": command,
            "time": time.time()
        }
        metadata["positions"]["bash_last"] = position
        self._write_metadata_unsafe(metadata)
    
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
    
    def mark_user_read(self) -> None:
        """Mark position for user read operation."""
        if not self._ensure_sync():
            return
            
        metadata = self._read_metadata_unsafe()
        if "positions" not in metadata:
            metadata["positions"] = {"bash_last": 0, "user_last": 0}
        metadata["positions"]["user_last"] = self._get_file_position()
        self._write_metadata_unsafe(metadata)
    
    # Reading operations
    
    def read_command_output(self, cmd_id: str, as_displayed: bool = False) -> str:
        """Read output for a specific command."""
        if not self._ensure_sync():
            return ""
            
        metadata = self._read_metadata_unsafe()
        cmd_info = metadata.get("commands", {}).get(cmd_id)
        
        if not cmd_info:
            return ""
            
        # Get positions
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
    
    def read_since_user_last(self, as_displayed: bool = False) -> str:
        """Read new content since last user read."""
        if not self._ensure_sync():
            return ""
            
        metadata = self._read_metadata_unsafe()
        last_pos = metadata.get("positions", {}).get("user_last", 0)
        current_pos = self._get_file_position()
        length = current_pos - last_pos
        
        if length <= 0:
            return ""
            
        if as_displayed:
            return self._render_stream_slice(last_pos, length)
        else:
            content = self._read_stream_slice(last_pos, length)
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
            
        # For line-based reading, we need to read the content first
        content = self.read_all(as_displayed=False)
        if not content:
            return ""
            
        lines_list = content.splitlines()
        if len(lines_list) <= lines:
            # Return all content
            if as_displayed:
                return self.read_all(as_displayed=True)
            else:
                return content
        
        # Find where the last N lines start
        last_lines = lines_list[-lines:]
        last_content = "\n".join(last_lines)
        
        if as_displayed:
            # Find byte position where these lines start
            prefix = "\n".join(lines_list[:-lines])
            start_pos = len(prefix.encode("utf-8")) + (1 if prefix else 0)  # +1 for newline
            length = len(content.encode("utf-8")) - start_pos
            return self._render_stream_slice(start_pos, length)
        else:
            return last_content


# Temporary - to be removed when ExecutorState is refactored
class StreamManager:
    """DEPRECATED: Temporary for backward compatibility."""
    def __init__(self, stream_dir: Path = None):
        self.stream_dir = stream_dir or Path("/tmp/termtap/streams")
    
    def get_stream(self, pane_id: str, session_window_pane: str) -> Stream:
        return Stream(pane_id, session_window_pane, self.stream_dir)