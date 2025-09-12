# Cross-Platform Process Tracking Strategy

## Current State

termtap uses `/proc` filesystem on Linux to determine process states, particularly wait channels that tell us WHY a process is sleeping (waiting for input vs executing code). This doesn't work on macOS/BSD which lack `/proc`.

## The Challenge

Different process states appear the same at a high level:
- Python waiting for user input: `sleeping` (ready ✅)
- Python executing `time.sleep()`: `sleeping` (busy ❌)
- Python waiting for subprocess: `sleeping` (busy ❌)

We need to know the specific syscall/wait channel to distinguish these states.

## Platform-Specific Capabilities

### Linux
- `/proc/{pid}/wchan` - Direct wait channel access (fast, reliable)
- `strace` - System call tracing (requires permissions)
- Full process tree via `/proc`

### macOS/BSD
- No `/proc` filesystem
- `sample` command - Call stack sampling (macOS only)
- `dtrace` - System tracing (requires sudo)
- `ps` with flags - Basic process states only
- `sysctl`/`libproc` - Native APIs for process info

### Cross-Platform Tools
- `psutil` - Python library wrapping native APIs
  - Provides process tree and basic states
  - BUT only gives 'running'/'sleeping', not wait channels
- Language-specific tools (see below)

## Proposed Architecture

### 1. Language-Specific Handlers with Native Tools

Each handler uses the best available tool for its language:

```python
handlers = {
    "python": {
        "linux": "/proc/wchan",           # Primary: fast, built-in
        "cross_platform": "py-spy",       # Fallback: if installed
        "default": "confirmation"         # Last resort: popups
    },
    "node": {
        "linux": "/proc/wchan",
        "cross_platform": "node --inspect-brk",  # Node debugger API
        "default": "confirmation"
    },
    "ruby": {
        "linux": "/proc/wchan",
        "cross_platform": "rbtrace",      # Ruby tracer
        "default": "confirmation"
    }
}
```

### 2. Graceful Degradation Strategy

For each process, try in order:
1. **Platform-native** - `/proc/wchan` on Linux
2. **Language-specific tool** - py-spy, jstack, etc. (if installed)
3. **Generic heuristics** - CPU usage, process age, output changes
4. **Confirmation handler** - Interactive popups (honest about uncertainty)

### 3. Implementation Example

```python
class _PythonHandler(ProcessHandler):
    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        # 1. Try Linux /proc (fastest, most accurate)
        if os.path.exists(f"/proc/{pane.process.pid}/wchan"):
            return self._check_wait_channel(pane)
        
        # 2. Try py-spy if available (cross-platform)
        if shutil.which("py-spy"):
            return self._check_pyspy(pane)
        
        # 3. Return None to let ConfirmationHandler take over
        return None, "cannot determine state"
```

## Tool Evaluation

### py-spy (Python)
- ✅ Cross-platform (Linux/macOS/Windows)
- ✅ Shows Python stack frames (can see `input()` vs `sleep()`)
- ✅ Fast (~10-50ms per check)
- ✅ No root required
- ❌ External dependency
- ❌ Python-specific only

### ptrace/dtrace (System-wide)
- ✅ Works for any process type
- ✅ Shows exact syscalls
- ❌ Requires root/sudo
- ❌ Complex parsing
- ❌ Performance overhead
- ❌ Platform-specific implementations

### psutil (Generic)
- ✅ Cross-platform
- ✅ Process tree support
- ✅ No subprocess calls
- ❌ No wait channel info
- ❌ Can't distinguish ready vs busy sleeping

## Current Implementation

As of v0.3.0, termtap uses a graceful degradation approach:

1. **Linux**: Full `/proc` filesystem support with wait channels
2. **macOS/BSD**: Returns `ProcessNode` with `wait_channel="no_proc"` marker
3. **Handler detection**: `ConfirmationHandler` automatically handles all processes with "no_proc" marker
4. **User experience**: Commands work on all platforms, with confirmation popups on macOS

## Future Enhancement: ps Command Fallback

For better macOS support without full /proc, we could use `ps` to get basic process info:

```python
def _get_process_info_macos(pid: int) -> Optional[ProcessNode]:
    """Get process info using ps command on macOS."""
    import subprocess
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pid,ppid,comm,state"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        # Parse ps output to create ProcessNode
        # Still mark with wait_channel="no_proc" 
        # But would have real process names
```

This would provide:
- Real process names (python3, node, ruby, etc.)
- Basic process state (R/S/Z)
- Parent-child relationships via PPID
- Still use ConfirmationHandler for state detection

## Recommendations

1. **Keep current Linux implementation** - `/proc/wchan` is optimal
2. **Current fallback works** - "no_proc" marker with ConfirmationHandler
3. **Future: Add ps command support** - Better process names on macOS
4. **Add optional py-spy support** for Python handler on macOS
5. **Document optional dependencies** - Users can install tools for better experience
6. **Avoid ptrace/dtrace** - Too heavy, requires permissions

## Future Enhancements

- Auto-detect and suggest installing language-specific tools
- Cache tool availability checks
- Add more language-specific handlers as needed
- Consider WebSocket/API approaches for modern apps

## Summary

The hybrid approach leverages platform strengths while maintaining usability:
- **Linux**: Full automatic state detection via `/proc`
- **macOS**: Language-specific tools where available, confirmation popups otherwise
- **All platforms**: Graceful degradation ensures termtap always works, just with varying levels of intelligence