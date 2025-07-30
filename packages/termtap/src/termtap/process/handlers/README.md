# Process Handler Development Guide

## Handler System Overview

Process handlers determine if a process is ready for input by examining its state. Each handler is responsible for a specific process type.

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

from . import ProcessHandler
from ..tree import ProcessNode


class _YourProcessHandler(ProcessHandler):
    """Handler for [process description]."""
    
    handles = ["process_name", "alternative_name"]
    
    def can_handle(self, process: ProcessNode) -> bool:
        """Check if this handler manages this process."""
        return process.name in self.handles
    
    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Determine if process is ready for input.
        
        Based on tracking data observations.
        """
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
```

### 3. Register Handler

Add to `handlers/__init__.py`:

```python
from .yourprocess import _YourProcessHandler

# In handler list initialization
_handlers = [
    _PythonHandler(),
    _SSHHandler(),
    _YourProcessHandler(),  # Add here
    _DefaultHandler(),  # Keep default last
]
```

### 4. Test

1. Exit and restart termtap
2. Run your process and verify detection:
   ```python
   bash("yourprocess", "test")
   ls()  # Check State column
   ```

## Handler Pattern Rules

1. **Class name**: `_ProcessNameHandler` (underscore prefix, internal)
2. **Module docstring**: Must include TESTING LOG with actual observations
3. **Check order**: Always check `has_children` first
4. **Return format**: `(bool, str)` - ready status and description
5. **Fallback**: Always provide default case

## Debugging

See `docs/DEBUGGING_GUIDE.md` for techniques to inspect process state directly.

## File Structure

```
handlers/
├── __init__.py      # Handler registry
├── base.py          # ProcessHandler base class
├── default.py       # Fallback handler
├── python.py        # Example: Python handler
├── ssh.py           # Example: SSH handler
└── yourprocess.py   # Your new handler
```