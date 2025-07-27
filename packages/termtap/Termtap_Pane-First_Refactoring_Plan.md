# Termtap Pane-First Refactoring Plan

## Core Philosophy
"Everything happens in panes, not sessions. Sessions are just containers for organizing panes."

## 1. Target System Overhaul

### New Target Format
```python
# Primary format: session:window.pane
"epic-swan:0.0"      # Explicit full path
"epic-swan:1.2"      # Window 1, pane 2
"%42"                # Direct pane ID (still supported)

# Convenience resolution (creature comfort)
"epic-swan"          → "epic-swan:0.0"    # Default to first pane
"epic-swan:1"        → "epic-swan:1.0"    # Default to first pane in window
```

### Benefits
- **Solves the edge case**: Target is now immutable - "epic-swan:0.0" always refers to THAT specific pane
- If pane moves, the target still points to the original location (which may be empty)
- Users explicitly choose which pane to target

## 2. ls() Command Enhancement

```
>>> ls()
Pane                  Session        Window  Shell   Process  State    Attached
--------------------  -------------  ------  ------  -------  -------  --------
epic-swan:0.0         epic-swan      main    bash    python3  working  Yes
epic-swan:1.0         epic-swan      logs    bash    tail     working  No
epic-swan:1.1         epic-swan      logs    bash    -        ready    No
test_python:0.0       test_python    main    bash    python   ready    No
_ddterm:0.0          _ddterm        main    fish    claude   working  Yes
```

Key changes:
- **Pane** column shows full `session:window.pane` identifier
- **Window** column shows window name (if set) or index
- Sorted by session, then window, then pane

## 3. Configuration Evolution

```toml
# termtap.toml - Pane-specific configs
[default]
dir = "."

# Session-level defaults (applied to all panes in session)
[sessions.backend]
dir = "./backend"
env = { NODE_ENV = "development" }

# Pane-specific overrides
[panes."backend:0.0"]
start = "npm run dev"
name = "server"  # Optional pane name

[panes."backend:0.1"] 
start = "npm run test:watch"
name = "tests"

[panes."backend:1.0"]
start = "tail -f logs/app.log"
name = "logs"
```

## 4. Streaming Architecture Changes

### Unified Stream Metadata
```python
@dataclass
class PaneMetadata:
    """Metadata for a pane's stream."""
    pane_id: str
    session_window_pane: str  # Full identifier
    
    # Command tracking
    command_marks: dict[str, StreamMark]  # bash() positions
    
    # Read tracking  
    read_positions: dict[str, int]  # Named read positions
    last_read: int  # Default read position
    
    # Stats
    stream_started: datetime
    last_activity: datetime
```

### Key Methods
```python
class StreamHandle:
    def read_since_last(self) -> str:
        """Read new content since last read() call."""
        
    def read_between_commands(self, start_cmd: str, end_cmd: str) -> str:
        """Read output between two command marks."""
        
    def read_command_output(self, cmd_id: str) -> str:
        """Read output from a specific command."""
```

## 5. Shared Stream, Separate Tracking

### Stream File Structure
```
/tmp/termtap/streams/
├── %42.stream          # Raw output from pane %42
├── %42.meta.json       # Metadata for tracking positions
├── %55.stream          # Raw output from pane %55
└── %55.meta.json       # Metadata for tracking positions
```

### Metadata Structure
```json
{
  "pane_id": "%42",
  "session_window_pane": "epic-swan:0.0",
  "stream_started": "2024-01-20T10:00:00Z",
  
  "bash_marks": {
    "cmd_abc123": {
      "position": 1024,
      "time": "2024-01-20T10:30:00Z",
      "command": "ls -la"
    },
    "cmd_def456": {
      "position": 2048,
      "time": "2024-01-20T10:31:00Z",
      "command": "npm test"
    }
  },
  
  "read_marks": {
    "last_read": {
      "position": 1536,
      "time": "2024-01-20T10:30:30Z"
    },
    "bookmarks": {
      "before_deploy": {"position": 1024},
      "after_test": {"position": 1800}
    }
  }
}
```

### Refactored bash() Command
```python
def bash(state: TermTapState, command: str, target: Target = "default", wait: bool = True, timeout: float = 30.0) -> dict:
    """Execute command in target pane."""
    # Resolve target to specific pane
    pane_id = resolve_target_to_pane(target)
    
    # Get or create stream for this pane
    stream = state.executor.stream_manager.get_stream(pane_id)
    if not stream.is_running():
        stream.start()
    
    # Mark position before sending command
    cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
    stream.mark_command(cmd_id, command)
    
    # Execute command
    send_keys(pane_id, command)
    
    if wait:
        # Wait for completion and read output
        wait_for_ready(pane_id, timeout)
        output = stream.read_from_mark(cmd_id)
        
        # IMPORTANT: Also mark this as a read position
        stream.mark_read("last_read")
    else:
        output = f"Command started in pane {pane_id}"
    
    # Detect process for syntax highlighting
    info = detect_process(pane_id)
    process = info.process or info.shell
    
    return {"process": process, "content": output}
```

### Refactored read() Command

#### Lazy Stream Initialization
The `read()` command now lazily initializes streams just like `bash()`, but gracefully falls back to direct tmux capture if no stream exists yet:

```python
def read(state: TermTapState, target: Target = "default", lines: int | None = None, since_last: bool = False) -> dict:
    """Read output from target pane."""
    # Resolve target to specific pane
    pane_id = resolve_target_to_pane(target)
    
    # Try to get existing stream (don't create yet)
    stream = state.executor.stream_manager.get_stream_if_exists(pane_id)
    
    # Determine read strategy based on stream existence and parameters
    if stream and stream.is_running():
        # Stream exists - use it for all operations
        if since_last:
            # Read only new content since last read() call
            content = stream.read_since_last()
        elif lines == -1:
            # Read entire stream file
            content = stream.read_all()
        elif lines:
            # Read last N lines from stream
            content = stream.read_last_lines(lines)
        else:
            # Default: read from last position to current
            content = stream.read_since_last()
        
        # Always update last read position
        stream.mark_read("last_read")
        
    else:
        # No stream yet - fall back to direct tmux capture
        if since_last:
            # Can't do since_last without stream, get visible instead
            content = capture_visible(pane_id)
            # Now start stream for future reads
            stream = state.executor.stream_manager.get_stream(pane_id)
            stream.start()
            stream.mark_read("last_read")
        elif lines == -1:
            # Get all available from tmux history
            content = capture_all(pane_id)
        elif lines:
            # Get last N lines from tmux
            content = capture_last_n(pane_id, lines)
        else:
            # Default: get visible
            content = capture_visible(pane_id)
    
    # Detect process for syntax highlighting
    info = detect_process(pane_id)
    process = info.process or info.shell
    
    return {"process": process, "content": content}
```

#### Read Behavior Scenarios

1. **First read() on a pane (no stream)**:
   ```python
   read("backend:0.0")  # Falls back to capture_visible()
   # Stream is created and started for future use
   ```

2. **After bash() has run**:
   ```python
   bash("npm test", "backend:0.0")  # Creates stream, marks position
   read("backend:0.0")              # Uses stream, reads from last mark
   ```

3. **Sequential reads with since_last**:
   ```python
   read("backend:0.0")                      # Read current state
   # ... time passes, more output appears ...
   read("backend:0.0", since_last=True)     # Only new content
   ```

4. **Mixed bash/read workflow**:
   ```python
   bash("npm install", "backend:0.0")       # Stream created, output marked as read
   # ... user does other things ...
   read("backend:0.0", since_last=True)     # Gets output since npm install finished
   bash("npm test", "backend:0.0")          # New command, new mark
   read("backend:0.0", lines=50)            # Last 50 lines from stream
   ```

### StreamHandle Methods
```python
class StreamHandle:
    def mark_command(self, cmd_id: str, command: str) -> None:
        """Mark position for a bash command."""
        pos = self._get_file_position()
        self.metadata["bash_marks"][cmd_id] = {
            "position": pos,
            "time": datetime.now().isoformat(),
            "command": command
        }
        self._save_metadata()
    
    def mark_read(self, mark_name: str = "last_read") -> None:
        """Mark position for a read operation."""
        pos = self._get_file_position()
        if mark_name == "last_read":
            self.metadata["read_marks"]["last_read"] = {
                "position": pos,
                "time": datetime.now().isoformat()
            }
        else:
            self.metadata["read_marks"]["bookmarks"][mark_name] = {"position": pos}
        self._save_metadata()
    
    def read_since_last(self) -> str:
        """Read new content since last read() call."""
        last_mark = self.metadata.get("read_marks", {}).get("last_read", {})
        last_pos = last_mark.get("position", 0)
        
        # Read from last position to current end of file
        current_content = self._read_from_position(last_pos)
        
        # If no previous read mark and no content, might be brand new stream
        if last_pos == 0 and not current_content:
            # Try to get some recent content from tmux as bootstrap
            return self._bootstrap_from_tmux()
        
        return current_content
    
    def read_from_mark(self, cmd_id: str) -> str:
        """Read output from a specific command mark."""
        mark = self.metadata.get("bash_marks", {}).get(cmd_id)
        if not mark:
            return ""
        return self._read_from_position(mark["position"])
```

### StreamManager Enhancement
```python
class StreamManager:
    def get_stream_if_exists(self, pane_id: str) -> StreamHandle | None:
        """Get stream only if it already exists."""
        return self.streams.get(pane_id)
    
    def get_stream(self, pane_id: str) -> StreamHandle:
        """Get or create stream for pane."""
        if pane_id not in self.streams:
            self.streams[pane_id] = StreamHandle(pane_id, self.stream_dir)
        return self.streams[pane_id]
```

## 6. API Changes

### Before (session-focused)
```python
bash("ls", target="backend")          # Which pane? Unclear
read("backend")                        # Reads from... somewhere?
```

### After (pane-explicit)
```python
bash("ls", target="backend:0.0")      # Explicit pane
bash("ls", target="backend")          # Convenience → backend:0.0

read("backend:0.0")                   # Read from specific pane
read("backend:0.0", since_last=True)  # Only new content
```

## 7. Implementation Steps

### Phase 1: Type System
- Update `Target` type to prefer `session:window.pane`
- Create `PaneIdentifier` class with parsing/validation
- Add resolution functions for convenience formats

### Phase 2: Pane Discovery
- Enhance tmux utils to list all panes with full identifiers
- Update `ls()` to show pane-centric view
- Add pane metadata to session info

### Phase 3: Stream Refactoring
- Update StreamHandle with unified metadata
- Implement read tracking separate from command marks
- Add `since_last` functionality to read()
- Implement graceful fallback for read() when no stream exists

### Phase 4: Config System
- Support both session-level and pane-level configs
- Implement config resolution hierarchy
- Add pane naming support

### Phase 5: Execute/Read Convergence
- Both use same streaming infrastructure
- Both resolve targets to specific panes
- Both track their operations independently
- bash() marks its output as "read" when returning

## 8. Migration Path

Since we're being ruthless:
1. Update all internal APIs to use pane identifiers
2. Keep convenience resolution but document as "comfort feature"
3. Update docs/examples to show pane-first approach
4. No backward compatibility - clean break

## 9. Benefits Summary

- **Precise targeting**: No ambiguity about which pane
- **Stable references**: Pane moves don't break targets  
- **Better workflows**: Can orchestrate multi-pane setups
- **Unified streaming**: One system for all output capture
- **Smart read tracking**: bash and read share position tracking
- **Graceful degradation**: Works even without existing streams
- **Future-proof**: Aligns with tmux's actual model

This plan makes termtap truly "pane-native" rather than "session-native with pane support".