# Termtap Streaming & Config Refactoring Plan

## Overview

This document outlines a comprehensive refactoring to align termtap with ReplKit2 patterns, implement proper streaming separation between bash() and read() operations, and maintain a minimal command set that grows organically with actual needs.

## Core Principles

1. **Data/Display Separation**: Commands return rich data; formatters control display
2. **Streaming Clarity**: Separate tracking for bash() vs read() operations  
3. **Config as Context**: Configuration provides project structure, not runtime behavior
4. **Minimal Command Set**: Start with bash, read, interrupt, ls, reload only
5. **YAGNI**: Add features only when patterns emerge from actual use

## 1. Type System Updates

### CommandResult Enhancement

```python
# In types.py
@dataclass
class CommandResult:
    """Result of command execution in a pane."""
    output: str
    status: CommandStatus
    pane_id: str
    session_window_pane: SessionWindowPane
    process: str | None
    command_id: str  # NEW: Unique identifier for this command
    duration: float | None = None  # NEW: Execution time if waited
    start_time: float | None = None  # NEW: When command started
```

### Read Mode Types (Start Simple)

```python
# In types.py
# Note: Start with just "direct" mode, add others when needed
type ReadMode = Literal["direct", "stream", "since_command"]
```

## 2. Streaming Architecture Updates

### Metadata Structure with Separate Tracking

```python
# In tmux/stream.py - Update default metadata
def _read_metadata(self) -> dict:
    """Read metadata from file. Returns empty dict if not exists."""
    if self.metadata_file.exists():
        try:
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    # Return default structure with SEPARATE tracking
    return {
        "pane_id": self.pane_id,
        "session_window_pane": self.session_window_pane,
        "stream_started": datetime.now().isoformat(),
        
        # Command tracking by ID
        "commands": {},  # cmd_id -> {position, end_position, time, command}
        
        # SEPARATE read positions - this is the key insight
        "positions": {
            "bash_last": 0,      # Last position after bash() command
            "user_last": 0,      # Last position after read() by user
            "stream_start": 0,   # When streaming began
        },
        
        # Named bookmarks for future advanced use
        "bookmarks": {},
        
        "last_activity": None
    }
```

### New Stream Methods for Separate Tracking

```python
# In tmux/stream.py
class _StreamHandle:
    def mark_command(self, cmd_id: str, command: str) -> None:
        """Mark position for a bash command."""
        metadata = self._read_metadata()
        pos = self._get_file_position()
        
        metadata["commands"][cmd_id] = {
            "position": pos,
            "time": datetime.now().isoformat(),
            "command": command,
            "end_position": None  # Updated when command completes
        }
        metadata["last_activity"] = datetime.now().isoformat()
        
        self._write_metadata(metadata)
    
    def mark_command_end(self, cmd_id: str) -> None:
        """Mark end position for a command."""
        metadata = self._read_metadata()
        if cmd_id in metadata["commands"]:
            end_pos = self._get_file_position()
            metadata["commands"][cmd_id]["end_position"] = end_pos
            metadata["positions"]["bash_last"] = end_pos  # Update bash position
            self._write_metadata(metadata)
    
    def mark_user_read(self) -> None:
        """Mark position for user read() operation - SEPARATE from bash."""
        metadata = self._read_metadata()
        metadata["positions"]["user_last"] = self._get_file_position()
        metadata["last_activity"] = datetime.now().isoformat()
        self._write_metadata(metadata)
    
    def read_since_user_last(self) -> str:
        """Read new content since last user read()."""
        metadata = self._read_metadata()
        last_pos = metadata["positions"].get("user_last", 0)
        return self._read_from_position(last_pos)
    
    def read_command_output(self, cmd_id: str) -> str:
        """Read output from specific command."""
        metadata = self._read_metadata()
        cmd_info = metadata["commands"].get(cmd_id)
        
        if not cmd_info:
            return ""
        
        start = cmd_info["position"]
        end = cmd_info.get("end_position", self._get_file_position())
        
        if not self.stream_file.exists():
            return ""
        
        with open(self.stream_file, "rb") as f:
            f.seek(start)
            content = f.read(end - start) if end > start else b""
        
        return content.decode("utf-8", errors="replace")
```

## 3. Core Module Updates

### Execute Function with Command Tracking

```python
# In core/execute.py
def execute(
    state: ExecutorState,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float = 30.0,
) -> CommandResult:
    """Execute command in tmux pane with hook support."""
    
    # Generate unique command ID
    cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
    start_time = time.time()
    
    # Resolve target to pane
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError:
        # Handle session creation for convenience targets
        if target == "default" or ":" in target or target.startswith("%"):
            return CommandResult(
                output=f"Target not found: {target}",
                status="running",
                pane_id="",
                session_window_pane="",
                process=None,
                command_id=cmd_id,
                start_time=start_time,
            )
        
        # Create new session for convenience format
        session = target
        config = get_pane_config(f"{session}:0.0")
        get_or_create_session(session, config.absolute_dir)
        pane_id, session_window_pane = resolve_target_to_pane(target)
    
    # Get stream for this pane
    stream = state.stream_manager.get_stream(pane_id, session_window_pane)
    
    if not stream.start():
        logger.error(f"Failed to start streaming for pane {pane_id}")

    # Mark command start
    stream.mark_command(cmd_id, command)

    # ... existing hook logic for before_send ...

    send_keys(pane_id, command)

    # ... existing hook logic for after_send ...

    if not wait:
        return CommandResult(
            output="",
            status="running",
            pane_id=pane_id,
            session_window_pane=session_window_pane,
            process=send_info.process if send_info.process else send_info.shell,
            command_id=cmd_id,
            start_time=start_time,
        )

    # ... wait loop with during_command hook ...

    # When command completes/times out
    output = stream.read_command_output(cmd_id)
    stream.mark_command_end(cmd_id)  # Mark completion
    duration = time.time() - start_time

    return CommandResult(
        output=output,
        status=status,  # completed/timeout/aborted
        pane_id=pane_id,
        session_window_pane=session_window_pane,
        process=final_info.process if final_info.process else final_info.shell,
        command_id=cmd_id,
        duration=duration,
        start_time=start_time,
    )
```

## 4. Module Structure

```
packages/termtap/src/termtap/
├── app.py               # App creation only
├── formatters.py        # Custom formatters (codeblock)
├── commands/
│   ├── __init__.py      # Import commands to trigger registration
│   ├── execution.py     # bash, interrupt
│   ├── inspection.py    # read, ls
│   └── utils.py         # reload
```

## 5. Formatter Implementation

### formatters.py

```python
"""Custom formatters for termtap displays."""

from typing import Any
from replkit2.types.core import CommandMeta
from replkit2.textkit.formatter import TextFormatter

from .app import app


@app.formatter.register("codeblock")
def format_codeblock(data: Any, meta: CommandMeta, formatter: TextFormatter) -> str:
    """Format command output as markdown code block.
    
    Expects data dict with:
    - content: The output to display
    - process: Language hint for syntax (optional)
    
    Other fields preserved for programmatic use.
    """
    if isinstance(data, dict) and "content" in data:
        process = data.get("process", "text")
        content = data.get("content", "")
        
        # Handle empty output
        if not content:
            return f"```{process}\n[No output]\n```"
        
        # Strip trailing whitespace but preserve formatting
        content = content.rstrip() if isinstance(content, str) else str(content)
        
        return f"```{process}\n{content}\n```"
    
    # Fallback for non-dict
    return f"```\n{str(data)}\n```"
```

## 6. Command Implementations

### commands/execution.py

```python
"""Command execution in tmux panes."""

from ..app import app
from ..types import Target
from ..core import execute
from ..tmux.utils import resolve_target_to_pane
from ..process import interrupt_process


@app.command(
    display="codeblock",
    fastmcp={"type": "tool", "description": "Execute command in tmux pane"},
)
def bash(
    state,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float = 30.0,
) -> dict:
    """Execute command in target pane.
    
    Returns rich data dict:
    - Display fields: content, process
    - Metadata: command_id, pane_id, session_window_pane, status, duration
    """
    result = execute(state.executor, command, target, wait, timeout)
    
    # Build display content
    if result.status == "running":
        content = f"Command started in pane {result.session_window_pane}"
    elif result.status == "timeout":
        content = f"{result.output}\n\n[Timeout after {timeout}s]"
    else:
        content = result.output
    
    # Return rich data structure
    return {
        # Display fields (used by formatter)
        "content": content,
        "process": result.process or "text",
        
        # Metadata fields (preserved for programmatic use)
        "command_id": result.command_id,
        "command": command,
        "pane_id": result.pane_id,
        "session_window_pane": result.session_window_pane,
        "status": result.status,
        "duration": result.duration,
        "target": target,  # Original target for convenience
    }


@app.command(
    fastmcp={"type": "tool", "description": "Send interrupt (Ctrl+C) to a pane"}
)
def interrupt(state, target: Target) -> str:
    """Send interrupt (Ctrl+C) to a pane."""
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return f"Failed to resolve target: {e}"
    
    success, message = interrupt_process(pane_id)
    if success:
        return f"{session_window_pane}: {message}"
    return f"Failed to interrupt {session_window_pane}: {message}"
```

### commands/inspection.py

```python
"""Pane inspection and output reading."""

from ..app import app
from ..types import Target, PaneRow, ProcessInfo
from ..tmux import capture_visible, capture_all, capture_last_n
from ..tmux.utils import resolve_target_to_pane, list_panes
from ..process import detect_process, detect_all_processes


@app.command(
    display="codeblock",
    fastmcp={
        "type": "resource",
        "description": "Read output from tmux pane",
        "uri": "bash://{target}/{lines}",
    },
)
def read(
    state,
    target: Target = "default",
    lines: int | None = None,
) -> dict:
    """Read output from target pane.
    
    Simple implementation - always uses direct tmux capture.
    Add streaming modes later if patterns emerge.
    
    Args:
        target: Target pane identifier
        lines: Number of lines (-1 for all, None for visible)
        
    Returns dict with content and metadata.
    """
    # Resolve target
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {
            "content": f"Error: {e}",
            "process": "text",
            "error": str(e)
        }
    
    # Direct tmux capture - simple and predictable
    if lines == -1:
        content = capture_all(pane_id)
    elif lines:
        content = capture_last_n(pane_id, lines)
    else:
        content = capture_visible(pane_id)
    
    # Detect process for syntax highlighting
    info = detect_process(pane_id)
    
    return {
        # Display fields
        "content": content,
        "process": info.process or info.shell,
        
        # Metadata
        "lines_read": len(content.splitlines()) if content else 0,
        "pane_id": pane_id,
        "session_window_pane": session_window_pane,
    }


@app.command(
    display="table",
    headers=["Pane", "Shell", "Process", "State", "Attached"],
    fastmcp={"enabled": False}  # REPL only for now
)
def ls(state) -> list[PaneRow]:
    """List all tmux panes with their current process."""
    panes = list_panes()
    pane_ids = [p.pane_id for p in panes]
    
    # Batch detect all processes in a single /proc scan
    process_infos = detect_all_processes(pane_ids)
    
    results = []
    for pane in panes:
        # Get process info from batch detection
        info = process_infos.get(
            pane.pane_id, 
            ProcessInfo(shell="unknown", process=None, state="unknown", pane_id=pane.pane_id)
        )
        
        results.append(PaneRow(
            Pane=pane.swp,
            Shell=info.shell,
            Process=info.process or "-",
            State=info.state,
            Attached="Yes" if pane.is_current else "No",
        ))
    
    return results
```

### commands/utils.py

```python
"""Utility commands."""

from ..app import app


@app.command(fastmcp={"enabled": False})
def reload(state) -> str:
    """Reload configuration from termtap.toml."""
    from .. import config
    config._config_manager = None
    return "Configuration reloaded"
```

### commands/__init__.py

```python
"""Termtap commands - minimal set."""

# Import to trigger @app.command decorators
from . import execution
from . import inspection
from . import utils

# Export for convenience
from .execution import bash, interrupt
from .inspection import read, ls
from .utils import reload

__all__ = ["bash", "interrupt", "read", "ls", "reload"]
```

## 7. Updated app.py

```python
"""termtap ReplKit2 application - pane-first architecture."""

from dataclasses import dataclass, field

from replkit2 import App

from .core import ExecutorState


@dataclass
class TermTapState:
    """Application state for termtap pane management."""
    executor: ExecutorState = field(default_factory=ExecutorState)


# Create the app (must be created before command imports)
app = App(
    "termtap",
    TermTapState,
    uri_scheme="bash",
    fastmcp={
        "name": "termtap",
        "description": "Terminal pane manager with tmux",
        "tags": {"terminal", "automation", "tmux"},
    },
)


# Import formatters and commands (triggers registration)
from . import formatters
from . import commands


if __name__ == "__main__":
    import sys
    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap")
```

## 8. Usage Examples

### Basic Usage (unchanged)
```python
>>> bash("npm test")  # Still simple
>>> read()           # Still simple
```

### New Capabilities
```python
>>> # Rich return values
>>> result = bash("pytest tests/", "backend")
>>> result["command_id"]
'cmd_abc123'
>>> result["duration"]
23.5

>>> # Future: Re-read command output (when pattern emerges)
>>> # read("backend", mode="since_command", since=result["command_id"])

>>> # Current: Just use bash and read
>>> bash("tail -f app.log", "monitor", wait=False)
>>> read("monitor")  # Simple tmux capture
```

## 9. Configuration Support (Context Only)

### Example termtap.toml
```toml
[default]
dir = "."
env = { PYTHONPATH = "." }
skip_processes = ["uv", "npm", "yarn", "poetry"]

[sessions.frontend]
dir = "./frontend"
env = { API_URL = "http://localhost:8000" }

[sessions.backend]
dir = "./backend"
env = { DATABASE_URL = "postgresql://localhost/myapp_dev" }
```

### How Config Helps
- Sessions created in correct directories
- Environment variables auto-set
- Process detection skips wrappers

### Usage Without Extra Commands
```python
# Let config handle context, use bash for actions
>>> bash("npm install", "frontend")  # Uses ./frontend dir
>>> bash("npm run dev", "frontend", wait=False)
>>> bash("pytest", "backend")  # Has DATABASE_URL set
```

## 10. Implementation Order

1. **Update types.py** - Add CommandResult fields
2. **Update tmux/stream.py** - Separate position tracking
3. **Update core/execute.py** - Command ID generation
4. **Create formatters.py** - Codeblock formatter
5. **Create commands/ structure** - Minimal command set
6. **Update app.py** - Just app creation and imports
7. **Test in REPL** - Verify rich return values work

## Benefits

1. **Clear Separation**: bash() and read() track positions independently
2. **Rich Metadata**: Commands return data for programmatic use
3. **Minimal Surface**: Only essential commands to start
4. **Growth Pattern**: Add commands when patterns emerge
5. **Config Context**: Project structure without runtime complexity
6. **ReplKit2 Aligned**: Proper data/display separation

This refactoring provides a solid foundation that can grow organically based on actual usage patterns while maintaining clarity and simplicity.