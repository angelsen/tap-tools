# tap-tools Development Guide

## Current Focus: termtap
Process-native tmux session manager with MCP support. Successor to debug-bridge's terminal tools.

### Key Features
- Auto-detects shell type and wraps non-bash commands
- Works with ANY tmux session (not just termtap-created ones)
- Process state detection using syscalls (no more "radio silence")
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
- `tmux/` - Pure tmux operations, no shell logic
- `process/` - Process detection and state analysis  
- `core/command.py` - All shell handling in ONE place
- `core/execute.py` - Clean orchestration

### Testing
```bash
# Run linting
ruff check packages/termtap/ --fix

# Test in REPL
bash("echo 'test'")  # Auto-detects shell, wraps if needed
status("cmd-id")     # Shows process tree and ready state
read("session-name", include_state=True)  # Rich process info
```

### ReplKit2 Integration
Built on ReplKit2 for dual REPL/MCP functionality:
- @/home/fredrik/Projects/Python/project-summer/replkit2/src/replkit2/llms.txt
- @/home/fredrik/Projects/Python/project-summer/replkit2/src/replkit2/textkit/README.md