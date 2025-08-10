# Termtap Known Issues

## Issue Summary

| ID | Title | Severity | Status | Component | Last Updated |
|---|---|---|---|---|---|
| [TERM-001](#term-001-stream-capture-pipe-failure) | Stream Capture Pipe Failure | Critical | Open | Streaming | 2025-08-08 |
| [TERM-002](#term-002-process-selection-with-sibling-processes) | Process Selection with Sibling Processes | Medium | Open | Process Tree | 2025-08-08 |

## Issue Severity Levels

- **Critical**: Core functionality broken, affects all users
- **High**: Major feature broken, workaround difficult
- **Medium**: Feature partially broken, workaround available
- **Low**: Minor issue, cosmetic or edge case

## Issue Status

- **Open**: Issue identified and documented
- **In Progress**: Active development to fix
- **Fixed**: Solution implemented and tested
- **Won't Fix**: Intentional behavior or out of scope

---

## TERM-001: Stream Capture Pipe Failure

- **ID**: TERM-001
- **Status**: Open
- **Severity**: Critical
- **Component**: Streaming
- **Discovered**: 2025-08-06
- **Last Updated**: 2025-08-08
- **Affects**: MCP mode, command output capture

### Problem Description

The tmux `capture-pane` pipe that feeds stream files can become stale/broken over time, causing stream capture to fail while command tracking continues working normally.

### Symptoms

- ✅ Commands execute successfully (visible in direct mode)
- ✅ Metadata is recorded correctly in JSON files (command IDs, positions, timestamps)
- ❌ Stream files stop growing (frozen at last captured position)
- ❌ All subsequent commands have identical start/end positions
- ❌ `execute()` commands return empty elements in MCP mode
- ❌ Stream-based output capture returns empty strings

### Root Cause Analysis

```
Command Execution Flow:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  mark_command   │──▶│  JSON metadata   │    │  Stream file    │
│   (working)     │    │   (working)      │    │   (broken)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       Records command info      Captures actual output
                       - cmd_id: "test123"       - "echo test\ntest\n$"
                       - position: 594            - Size: STUCK at 594
                       - command: "echo test"     - No new content
```

**Why Output Is Empty**:
1. Command recorded with `position: 594, end_position: 594`
2. Stream file frozen at 594 bytes (no new content appended)
3. `read_command_output()` extracts text between positions 594-594 → empty string
4. `execute()` result: `if result["output"]:` → false → no elements

### Current Workaround

**Manual stream restart**:
```python
stream = Stream(pane_id, session_window_pane, stream_dir)
stream.stop()   # Kill broken pipe
stream.start()  # Create fresh tmux capture-pane pipe
```

**Verification**:
- Stream file size should increase after new commands
- Commands should return proper output in elements

### Proposed Solutions

1. **Auto-Recovery**: Implement stream health checks in `ensure_streaming()`
2. **Monitoring**: Detect stream health without manual inspection
3. **Fallback**: Use direct capture when streaming is broken
4. **Diagnostics**: Add commands to check stream status

### Files Affected

- `packages/termtap/src/termtap/tmux/stream.py` - Stream management
- `packages/termtap/src/termtap/pane/streaming.py` - Pane integration  
- `packages/termtap/src/termtap/pane/execution.py` - Command execution
- `packages/termtap/src/termtap/commands/bash.py` - MCP tool affected

### Test Case

```python
# In termtap REPL:
from termtap.pane import Pane
from termtap.tmux import resolve_or_create_target

pane_id, swp = resolve_or_create_target("default")
pane = Pane(pane_id)

# Check if stream is frozen
from termtap.pane.streaming import mark_command_start, get_command_output
cmd_id = mark_command_start(pane, "echo 'test'")
# Send command manually, then:
output = get_command_output(pane, cmd_id)
print(f"Output: {repr(output)}")  # Should be empty if stream is broken

# Check metadata vs stream file size
from pathlib import Path
import json
stream_dir = Path("/tmp/termtap/streams")
json_file = stream_dir / f"{pane_id}.json"
stream_file = stream_dir / f"{pane_id}.stream"

with open(json_file) as f:
    metadata = json.load(f)
    
print(f"Commands in metadata: {len(metadata.get('commands', {}))}")
print(f"Stream file size: {stream_file.stat().st_size}")
# If many commands but small static file size → pipe is broken
```

---

## TERM-002: Process Selection with Sibling Processes

- **ID**: TERM-002
- **Status**: Open
- **Severity**: Medium
- **Component**: Process Tree
- **Discovered**: 2025-08-08
- **Last Updated**: 2025-08-08
- **Affects**: Process detection, handler selection

### Problem Description

When users suspend termtap processes with Ctrl+Z, the system creates sibling process trees where the original process is suspended but new active processes continue execution. The current process scanning only follows the first child chain and cannot discover active sibling processes.

### Symptoms

- ✅ Suspended processes are ignored (no crashes/timeouts)
- ❌ Active sibling processes not discovered for monitoring  
- ❌ Falls back to `_DefaultHandler` instead of proper process-specific handler
- ❌ Process shows as `None` instead of detecting active termtap instance

### Root Cause Analysis

**Process Tree Example**:
```
bash (687041)
├── uv (1252654) [T - stopped] ← First chain (suspended)
│   └── termtap (1252658) [T - stopped]
└── uv (1418398) [S+ - active] ← Sibling chain (active, not discovered)
    └── termtap (1418402) [S+ - active]
```

**Code Issue**:
`get_process_chain()` in `process/tree.py` uses single-chain traversal:
```python
# Current: follows only first child at each level
current = current.children[0] if current.children else None
```

This misses sibling branches where active processes may exist.

### How to Reproduce

1. User runs termtap MCP: `uv run termtap --mcp`
2. User presses Ctrl+Z to suspend (creates background job)  
3. User runs new termtap REPL: `uv run termtap`
4. Process scanning finds first (suspended) chain, misses second (active) chain

### Current Workaround

Manual job control management:
```bash
jobs -l        # List background jobs
fg %1          # Resume suspended process
# OR
kill %1        # Kill suspended background job
```

### Proposed Solutions

**Option A: Multi-branch Process Discovery**
```python
def _select_best_process(candidates: List[ProcessNode]) -> Optional[ProcessNode]:
    """Select best active process, ignoring stopped/zombie processes."""
    active = [p for p in candidates if p.state not in ["T", "Z"]]
    if not active:
        return None
    # Prefer running > sleeping > other active states
    running = [p for p in active if p.state == "R"]
    return running[0] if running else active[0]
```

**Option B: Sibling-Aware Chain Discovery**
- Explore all child branches from shell process
- Collect process chains from all branches  
- Select chain with active processes over suspended ones

**Option C: Process State Filtering** (Current)
- Filter stopped processes in chain traversal
- Simpler approach, handles suspended process case
- May miss some active sibling processes

### Files Affected

- `packages/termtap/src/termtap/process/tree.py` - Process chain discovery
- `packages/termtap/src/termtap/pane/core.py` - Process property access
- `packages/termtap/src/termtap/process/handlers/__init__.py` - Handler selection

---

## Contributing

When adding a new issue:
1. Assign next ID in sequence (TERM-XXX)
2. Update the Issue Summary table
3. Use the template structure
4. Include reproduction steps if possible
5. Document any workarounds