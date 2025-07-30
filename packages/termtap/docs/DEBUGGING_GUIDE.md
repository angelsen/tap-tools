# Termtap Debugging Guide

This guide documents useful debugging techniques for troubleshooting termtap issues, particularly around process detection and command execution.

## Using Termtap REPL for Debugging

Since termtap runs as a Python REPL, you can import and use its internal modules directly for debugging.

### Essential Imports

```python
# Import debugging utilities
from termtap.tmux import get_pane_pid, get_pane_info, list_panes
from termtap.process.detector import detect_process
from termtap.process.tree import get_process_chain, get_process_tree
from termtap.process.handlers import get_handler
from termtap.config import get_execution_config
```

### Finding Panes

```python
# List all panes to find the one you need
from termtap.tmux import list_panes
panes = list_panes()
for p in panes:
    if p.session == "test-session":
        print(f"Found: {p.pane_id} -> {p.swp}")
```

### Debugging Process Detection

```python
# Get detailed process information
pid = get_pane_pid("%9")  # Replace with actual pane ID
print(f"Pane PID: {pid}")

# Get process chain to see parent-child relationships
chain = get_process_chain(pid)
print("\nProcess chain:")
for proc in chain:
    print(f"  {proc.pid}: {proc.name} (wait: {proc.wait_channel})")
```

### Understanding Process State Detection

```python
# Check what the detector sees
proc_info = detect_process("%9")
print(f"Process: {proc_info.process}")
print(f"Shell: {proc_info.shell}")
print(f"State: {proc_info.state}")

# Check handler logic for specific process
python_proc = None
for proc in chain:
    if proc.name == "python3":
        python_proc = proc
        break

if python_proc:
    from termtap.process.handlers.python import _PythonHandler
    handler = _PythonHandler()
    is_ready, reason = handler.is_ready(python_proc)
    print(f"Handler says: ready={is_ready}, reason='{reason}'")
```

### Checking Configuration

```python
# Check execution config for a pane
from termtap.config import get_execution_config
config = get_execution_config("test-session:0.0")
print(f"Ready pattern: {config.ready_pattern}")
print(f"Timeout: {config.timeout}")
```

## Common Issues and Solutions

### Python REPL Hanging

**Symptom**: `bash("python3", target)` hangs until timeout

**Cause**: Python REPL wait channel not recognized as "ready"

**Debug steps**:
1. Check the wait channel:
   ```python
   chain = get_process_chain(pid)
   for proc in chain:
       if proc.name == "python3":
           print(f"Wait channel: {proc.wait_channel}")
   ```

2. Common wait channels for Python REPL:
   - `do_sys_poll` - Traditional, recognized by default
   - `do_select` - Newer systems, needs to be added to handler

**Solution**: Update Python handler to recognize additional wait channels

### Multiline Command Issues

**Symptom**: Multiline commands not executing properly in REPLs

**Debug steps**:
1. Check if command contains newlines:
   ```python
   command = """def foo():
       return 42"""
   print(f"Has newlines: {'\\n' in command}")
   ```

2. Verify buffer approach is being used:
   - Single-line commands use `send_keys`
   - Multiline commands use `send_via_paste_buffer`

3. Test buffer directly:
   ```python
   from termtap.tmux import send_via_paste_buffer
   send_via_paste_buffer(pane_id, multiline_command)
   ```

### Process Not Detected

**Symptom**: `ls()` shows wrong process or "-"

**Debug steps**:
1. Check process chain:
   ```python
   chain = get_process_chain(pid)
   for i, proc in enumerate(chain):
       print(f"{i}: {proc.name} (pid={proc.pid})")
   ```

2. Check if process is in skip list:
   ```python
   from termtap.types import KNOWN_SHELLS
   print(f"Known shells: {KNOWN_SHELLS}")
   ```

## Testing Handler Changes

When modifying process handlers, you need to reload termtap:

1. Exit the REPL: `exit()`
2. Restart: `uv run termtap`
3. Test the updated behavior

## Advanced Debugging

### Monitoring Process State Changes

```python
import time

# Monitor process state over time
for i in range(5):
    proc_info = detect_process(pane_id)
    chain = get_process_chain(get_pane_pid(pane_id))
    python_proc = next((p for p in chain if p.name == "python3"), None)
    if python_proc:
        print(f"{i}s: state={proc_info.state}, wait={python_proc.wait_channel}")
    time.sleep(1)
```

### Checking Buffer Operations

```python
# Test buffer naming
import hashlib
content = "test content"
buffer_name = f"tt_{hashlib.md5(content.encode()).hexdigest()[:8]}"
print(f"Buffer name: {buffer_name}")

# List tmux buffers (run in bash)
bash("tmux list-buffers", wait=False)
read()
```

## Tips

1. **Use `wait=False` for debugging**: When testing commands that might hang, use `wait=False` and then `read()` to check output

2. **Check logs in real-time**: Use `read(target, mode="stream")` to monitor ongoing output

3. **Inspect raw process info**: The `/proc` filesystem has detailed process information:
   ```python
   bash(f"cat /proc/{pid}/stat", wait=False)
   ```

4. **Test handlers in isolation**: Import and test handler methods directly as shown above

This debugging approach helped identify and fix the Python REPL `do_select` wait channel issue, demonstrating the power of having direct REPL access to termtap's internals.