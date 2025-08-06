# Process Handler Development Guide

## Handler System Overview

Process handlers determine if a process is ready for input by examining pane state. Each handler is responsible for a specific process type and operates on `Pane` objects.

## Adding a New Handler

### 1. Track the Process

Use the `track` command to collect data:

```python
track("yourprocess", duration=10)
```

This saves:
- `~/.termtap/tracking/[timestamp]_[slug]/metadata.json` - System information
- `~/.termtap/tracking/[timestamp]_[slug]/timeline.json` - Process states over time
- `~/.termtap/tracking/[timestamp]_[slug]/screenshots/` - Terminal captures

### 2. Create Handler File

Create `handlers/yourprocess.py` following this exact structure:

```python
"""[Process name] handler - [one line description].

Internal module - no public API.

TESTING LOG:
Date: [YYYY-MM-DD]
System: [OS and version from metadata.json]
Process: [process version]
Tracking: [path to your tracking data]

Observed wait_channels:
- [wait_channel]: [when this occurred] ([ready/working])
- [wait_channel]: [when this occurred] ([ready/working])

Notes:
- [Any important observations]
"""

from ..pane import Pane


class _YourProcessHandler:
    """Handler for [process description]."""
    
    handles = ["process_name", "alternative_name"]
    
    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages this pane's process."""
        if not pane.process:
            return False
        return pane.process.name in self.handles
    
    def is_ready(self, pane: Pane) -> tuple[bool, str]:
        """Determine if pane's process is ready for input.
        
        Based on tracking data observations.
        """
        process = pane.process
        if not process:
            return True, "No active process"
        
        # Check children first - most reliable
        if process.has_children:
            return False, f"{process.name} has subprocess"
        
        # Add wait_channel checks based on your tracking
        if process.wait_channel == "observed_ready_channel":
            return True, f"{process.name} ready"
            
        if process.wait_channel == "observed_working_channel":
            return False, f"{process.name} working"
            
        # Default fallback
        return False, f"{process.name} {process.wait_channel or 'running'}"
    
    def filter_output(self, output: str) -> str:
        """Filter output for this process type."""
        return output  # Override if needed
    
    def before_send(self, pane: Pane, command: str) -> str:
        """Modify command before sending."""
        return command  # Override if needed
    
    def after_send(self, pane: Pane, command: str) -> None:
        """Hook after command sent."""
        pass  # Override if needed
    
    def during_command(self, pane: Pane, elapsed: float) -> bool:
        """Check if should continue waiting."""
        return True  # Override to abort on conditions
    
    def after_complete(self, pane: Pane, command: str, elapsed: float) -> None:
        """Hook after command completes."""
        pass  # Override if needed
    
    def interrupt(self, pane: Pane) -> tuple[bool, str]:
        """Send interrupt signal."""
        from ...tmux.pane import send_keys
        success = send_keys(pane.pane_id, "C-c")
        return success, "Sent Ctrl+C"
```

### 3. Register Handler

Add to `handlers/__init__.py`:

```python
from .yourprocess import _YourProcessHandler

# In get_handler function
def get_handler(pane: Pane):
    """Get handler for pane's current process."""
    handlers = [
        _PythonHandler(),
        _SSHHandler(),
        _YourProcessHandler(),  # Add here
        _DefaultHandler(),  # Keep default last
    ]
    
    for handler in handlers:
        if handler.can_handle(pane):
            return handler
    
    return _DefaultHandler()
```

### 4. Test

1. Exit and restart termtap
2. Run your process and verify detection:
   ```python
   bash("yourprocess", "test")
   ls()  # Check State column
   track("test")  # Monitor handler behavior
   ```

## Handler Interface

All handlers should implement these methods:

- `can_handle(pane: Pane) -> bool` - Check if handler manages this pane
- `is_ready(pane: Pane) -> tuple[bool, str]` - Determine ready state
- `filter_output(output: str) -> str` - Filter/clean output
- `before_send(pane: Pane, command: str) -> str` - Modify command before sending
- `after_send(pane: Pane, command: str) -> None` - Hook after send
- `during_command(pane: Pane, elapsed: float) -> bool` - Continue waiting check
- `after_complete(pane: Pane, command: str, elapsed: float) -> None` - Completion hook
- `interrupt(pane: Pane) -> tuple[bool, str]` - Send interrupt signal

## Handler Pattern Rules

1. **Class name**: `_ProcessNameHandler` (underscore prefix, internal)
2. **Module docstring**: Must include TESTING LOG with actual observations
3. **Check order**: Always check `has_children` first
4. **Return format**: `(bool, str)` - ready status and description
5. **Fallback**: Always provide default case
6. **Pane access**: Use `pane.process` for current process info

## Content-Based Detection

Handlers can also use `pane.visible_content` for state detection:

```python
def is_ready(self, pane: Pane) -> tuple[bool, str]:
    """Check if ready based on visible content."""
    content = pane.visible_content
    
    if ">>> " in content:  # Python prompt
        return True, "Python REPL ready"
    
    if "In [" in content:  # IPython prompt
        return True, "IPython ready"
    
    # Fall back to process-based detection
    return self._check_process_state(pane)
```

## File Structure

```
handlers/
├── __init__.py      # Handler registry and get_handler()
├── default.py       # Fallback handler
├── python.py        # Python/IPython handler
├── ssh.py           # SSH session handler
├── claude.py        # Claude CLI handler
└── yourprocess.py   # Your new handler
```