# Pane Module Implementation Plan

## Vision
The Pane is the fundamental unit of termtap. Everything else exists to support pane operations.

## Core Principles

1. **Pane-First Architecture**: Every operation starts with a Pane
2. **No Backwards Compatibility**: Existing modules change to serve the pane module
3. **Ruthless Simplicity**: If it doesn't directly support pane operations, delete it
4. **Pure Data + Functions**: Pane class holds data, functions perform operations
5. **Test-Driven**: Test each phase before moving to the next

## Implementation Phases

### Phase 1: Core Foundation (Day 1)
Create the pure data Pane class with lazy properties.

**Files to create:**
- `pane/__init__.py` - Exports
- `pane/core.py` - Pane dataclass

**Existing modules to modify:**
- NONE - First establish the foundation

**Test checkpoint:**
```python
>>> from termtap.pane import Pane
>>> p = Pane("%5")
>>> p.session_window_pane  # Should work
>>> p.process  # Should work
```

### Phase 2: Execution Layer (Day 1)
Add command execution with handler support.

**Files to create:**
- `pane/execution.py` - send_command, interrupt

**Existing modules to refactor:**
- `tmux/pane.py` - Remove send_keys/send_via_paste_buffer duplication, pane module calls them
- `process/handlers/base.py` - Change handler methods to accept Pane directly:
  ```python
  def is_ready(self, pane: Pane) -> tuple[bool, str]:
      # Use pane.process, pane.visible_content, etc.
  ```
- Delete ProcessContext from types.py - handlers use Pane directly

**Test checkpoint:**
```python
>>> from termtap.pane import Pane, send_command
>>> p = Pane("%5")
>>> result = send_command(p, "echo hello")
>>> print(result['output'])
```

### Phase 3: Inspection Layer (Day 1)
Add output reading and process inspection.

**Files to create:**
- `pane/inspection.py` - read_output, get_process_info
- `pane/streaming.py` - Stream management

**Existing modules to refactor:**
- `tmux/stream.py` - Becomes internal to pane module, simplified interface
- `process/detector.py` - Delete detect_process, replace with pane.is_ready property
- `core/execute.py` - Delete entirely, pane/execution.py replaces it

**Test checkpoint:**
```python
>>> from termtap.pane import Pane, read_output
>>> p = Pane("%5")
>>> output = read_output(p, lines=10)
```

### Phase 4: Command Migration (Day 2)
Migrate all commands to use pane module.

**Commands to refactor (in order):**

1. **bash.py**
   ```python
   def bash(state, command: str, target: Target = "default", ...):
       pane = Pane(resolve_or_create_target(target))
       return format_result(send_command(pane, command, ...))
   ```

2. **read.py**
   ```python
   def read(state, target: Target = "default", ...):
       pane = Pane(resolve_target(target))
       return format_output(read_output(pane, ...))
   ```

3. **interrupt.py**
   ```python
   def interrupt(state, target: Target = "default"):
       pane = Pane(resolve_target(target))
       return "Interrupted" if interrupt(pane) else "Failed"
   ```

4. **ls.py**
   ```python
   def ls(state):
       return [get_pane_info(Pane(pid)) for pid in list_pane_ids()]
   ```

5. **track.py**
   ```python
   def track(state, *commands, target: Target = "default", ...):
       pane = Pane(resolve_target(target))
       # Use pane for all tracking operations
   ```

**Existing modules to refactor:**
- `tmux/resolution.py` - Make resolve_target return just pane_id, not tuple
- `tmux/structure.py` - Simplify to just list pane IDs
- Delete `types.py` ProcessInfo - use pane properties instead

### Phase 5: Init System Refactor (Day 2)
Update init to use pane-centric approach.

**Files to refactor:**
- `commands/init.py` - Services tracked as list of Panes
- `config.py` - Simplify ExecutionConfig, pane module handles details

**New pattern:**
```python
# init.py
services = {}  # name -> Pane
for service in init_group.services:
    pane = Pane(create_pane(...))
    services[service.name] = pane
    send_command(pane, service.command, ...)
```

### Phase 6: Final Cleanup (Day 3)
Remove all obsolete code.

**To delete entirely:**
- `core/` directory - pane module replaces it
- `types.py` - ProcessContext, ProcessInfo, etc.
- `process/detector.py` - pane properties replace it
- Any tmux functions that duplicate pane operations

**To simplify:**
- `process/tree.py` - Keep only what pane.process_chain needs
- `tmux/` - Keep only primitive operations pane module uses

## Module Relationships After Refactor

```
pane/
├── core.py         # Pane class with lazy properties
├── execution.py    # Uses: tmux/pane.py, process/handlers/
├── inspection.py   # Uses: tmux/pane.py
└── streaming.py    # Uses: tmux/stream.py

commands/
├── bash.py         # Uses: pane.Pane, pane.send_command
├── read.py         # Uses: pane.Pane, pane.read_output
├── ls.py           # Uses: pane.Pane, pane properties
└── ...             # All use pane module

tmux/               # Reduced to primitive operations
├── core.py         # run_tmux only
├── pane.py         # capture_pane, send_keys primitives
└── session.py      # session management

process/            # Simplified to support pane
├── tree.py         # get_process_chain for pane.process_chain
└── handlers/       # Accept Pane objects directly
```

## Testing Strategy

Each phase has a test checkpoint. Run these in tap-tools-terminal:

```python
# After Phase 1
from termtap.pane import Pane
p = Pane("%5")
assert p.session_window_pane.endswith(":0.0")
assert p.process is not None

# After Phase 2  
from termtap.pane import send_command
result = send_command(p, "echo test")
assert result['status'] == 'completed'
assert 'test' in result['output']

# After Phase 3
from termtap.pane import read_output
output = read_output(p)
assert len(output) > 0

# After Phase 4
from termtap import bash
bash("echo refactored")  # Should work with new pane module
```

## Success Criteria

1. **Simplicity**: Each command file < 50 lines
2. **Performance**: Lazy loading prevents unnecessary work
3. **Clarity**: `pane = Pane(id); send_command(pane, cmd)` is self-explanatory
4. **Testability**: Can test pane operations in REPL without full app
5. **No Coupling**: Pane module doesn't import from commands/

## Guidelines During Implementation

1. **Start small**: Get Phase 1 working perfectly before moving on
2. **Test constantly**: Use tap-tools-terminal REPL for immediate feedback
3. **Delete fearlessly**: If something doesn't serve the pane module, remove it
4. **No defensive code**: Pane("%invalid") should fail fast
5. **Handler refactor**: Make handlers accept Pane, not ProcessContext
6. **One source of truth**: If pane has the info, delete it everywhere else

## Potential Issues & Solutions

**Issue**: Circular imports between pane and other modules
**Solution**: Pane module only imports from tmux/ and process/tree.py

**Issue**: Stream manager requires app state
**Solution**: Pass app state to streaming functions, or make stream manager global

**Issue**: Handlers currently expect ProcessContext
**Solution**: Phase 2 changes handlers to accept Pane directly

**Issue**: Many places expect (pane_id, session_window_pane) tuples  
**Solution**: Change them all to just return/accept pane_id

## The End State

After implementation, using termtap becomes:

```python
from termtap.pane import Pane, send_command, read_output

# Everything starts with a Pane
pane = Pane("%5")

# All operations are functions on that pane
result = send_command(pane, "ls -la")
output = read_output(pane, lines=50)

# Pane has all the info you need
print(f"Running {pane.process.name} in {pane.session}")
```

Simple. Clear. Ruthless.