# tap-tools Development Guide

## Current Focus: termtap
Process-native tmux session manager with MCP support. Successor to debug-bridge's terminal tools.

### Key Features
- Auto-detects shell type and wraps non-bash commands
- Works with ANY tmux session (not just termtap-created ones)
- Process state detection using pstree algorithm (accurate child tracking)
- First non-shell process display in ls() output
- Docker-style session names by default
- Pattern-based hover dialogs for dangerous commands

### Development Workflow
Rapid REPL development using debug-bridge:
```python
# Primary session for testing
mcp__debug-brdige__terminal_send(session_id="epic-swan", command="uv run python -m termtap")
mcp__debug-brdige__terminal_read(session_id="epic-swan", lines=50)
```

### Architecture
- `pane/` - Pane-centric core with lazy-loaded properties
  - `core.py` - Pure data `Pane` class
  - `execution.py` - Command execution with handler lifecycle
  - `inspection.py` - Output reading and process info
  - `streaming.py` - Stream-based output tracking
- `tmux/` - Pure tmux operations, no shell logic
- `process/` - Process detection using pstree algorithm
  - `tree.py` - Builds complete process trees from /proc
  - `handlers/` - Process-specific handlers accepting `Pane` objects
- `commands/` - REPL commands using pane-centric API
- `app.py` - ReplKit2 app with MCP tools/resources

### Style Guide
When working on termtap code, follow these conventions to maintain consistency:

1. **Naming**: Add underscore prefix to ALL non-public functions (helps users distinguish internal vs public API)
2. **Exports**: `__init__.py` must import/export ONLY PUBLIC API items (prevents linting errors)
3. **Docstrings**: Module docs list PUBLIC API only; use provided templates (ensures clear documentation)
4. **Comments**: Explain WHY not WHAT (code shows what, comments explain reasoning)
5. **Workflow**: First `make format`, then `make conform-module TARGET=path`, then fix any errors

### Design Philosophy
**Don't recreate what syscalls already tell us.** Termtap is "process-native" - leverage OS-level information:

- Process tree built using pstree algorithm (scanning /proc/*/stat for PPID relationships)
- First non-shell process selection for meaningful display names
- Use `/proc` information instead of pattern matching when possible
- Query tmux state directly rather than maintaining shadow state
- Only create types/abstractions for: unique identifiers, configuration, UI contracts, and API structures
- Avoid duplicating information already available from the system

### Testing
```bash
# Run linting and type checking
ruff check packages/termtap/ --fix
basedpyright packages/termtap/

# Test in REPL
bash("echo 'test'")     # Auto-detects shell, wraps if needed
ls()                    # Shows sessions with first non-shell process
read("session-name")    # Get session output
run("demo")            # Run service group from termtap.toml
interrupt("demo.backend") # Service name resolution
```

### ReplKit2 Integration
Built on ReplKit2 for dual REPL/MCP functionality:
- @/home/fredrik/Projects/Python/project-summer/replkit2/src/replkit2/llms.txt
- @/home/fredrik/Projects/Python/project-summer/replkit2/src/replkit2/textkit/README.md

### Pane-Centric Implementation
The entire termtap architecture is built around the `Pane` abstraction:
- Everything operates through `Pane` objects with lazy-loaded properties
- Handlers accept `Pane` directly for process-specific behavior
- 70% performance improvement through optimized process scans
- Unified execution path with consistent return formats