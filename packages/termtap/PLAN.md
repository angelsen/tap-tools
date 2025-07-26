# termtap Architecture

## Overview
Process-native tmux session manager with MCP support. Built on ReplKit2 for dual REPL/MCP functionality, using a handler-based architecture for intelligent process detection.

## Core Design Principles

1. **Process-Native**: Leverage OS-level syscalls instead of pattern matching
2. **Clean Module Boundaries**: Public APIs only, no cross-module private function usage
3. **Streaming Sidecar**: Reliable output capture through tmux pipe streams
4. **Handler Architecture**: Extensible system for different process types
5. **Minimal State**: No command tracking, just stream management

## Architecture

### Module Structure
```
packages/termtap/src/termtap/
├── __init__.py          # Package exports (app, __version__)
├── __main__.py          # Entry point for python -m termtap
├── app.py               # ReplKit2 app with commands
├── config.py            # Configuration with skip_processes support
├── types.py             # Type definitions (Target, CommandStatus, ProcessInfo, etc.)
├── core/
│   ├── __init__.py      # Exports: execute, ExecutorState, CommandResult
│   ├── control.py       # Internal process control functions
│   └── execute.py       # Command execution with streaming
├── tmux/
│   ├── __init__.py      # Exports all tmux functions and exceptions
│   ├── session.py       # Session management
│   ├── pane.py          # Pane capture functions  
│   ├── stream.py        # Streaming sidecar for output
│   ├── utils.py         # Low-level tmux operations
│   ├── names.py         # Session name generation
│   └── exceptions.py    # TmuxError, SessionNotFoundError, CurrentPaneError
├── process/
│   ├── __init__.py      # Exports process detection functions
│   ├── detector.py      # Process state detection
│   ├── tree.py          # Process tree analysis
│   └── handlers/        # Pluggable handlers per process type
│       ├── __init__.py  # Exports: ProcessHandler, get_handler
│       ├── default.py   # Generic process handler
│       ├── python.py    # Python REPL/script handler
│       └── ssh.py       # SSH session handler with safety
└── hover/               # Interactive dialogs (used by handlers)
    ├── __init__.py      # Exports: show_hover
    └── dialog.sh        # Shell script for hover UI
```

### Key APIs

#### app.py - ReplKit2 Commands
- `bash(command, target, wait, timeout)` - Execute with streaming output (MCP tool)
- `read(target, lines)` - Direct tmux capture (MCP resource)
- `ls()` - List sessions with process info (REPL only)
- `interrupt(session)` - Send Ctrl+C (MCP tool)
- `reload()` - Reload configuration (REPL only)

#### tmux Module - Public API
- `list_sessions()` - Get all sessions
- `session_exists()`, `get_or_create_session()`, `kill_session()`
- `capture_visible()`, `capture_all()`, `capture_last_n()`
- `get_pane_pid()`, `get_pane_for_session()`
- `send_keys()` - Send keystrokes
- `TmuxError`, `SessionNotFoundError`, `CurrentPaneError` - Exception types

#### process Module - Public API
- `detect_process(session)` - Get current process info for a session
- `detect_all_processes(sessions)` - Batch process detection
- `interrupt_process(session)` - Interrupt with appropriate handler
- `get_handler_for_session(session, process_node)` - Get handler for process
- `ProcessHandler` - Base class for process handlers
- `get_handler(process)` - Get handler instance

#### core Module - Public API
- `execute(state, command, target, wait, timeout)` - Main execution
- `ExecutorState` - State container with StreamManager
- `CommandResult` - Result type with output, status, session, process

### Streaming Architecture

The streaming sidecar provides reliable output capture:
1. Mark position before sending command
2. Send command via tmux send-keys
3. Stream captures all output to file
4. Read from mark when ready/timeout

This avoids tmux capture timing issues and provides complete output.

### Handler System

Process handlers in `process/handlers/` provide:
- Process type detection
- Ready state determination  
- Pre/post command hooks
- Custom behavior per process type

Current handlers:
- `default.py` - Generic processes (simple "no children = ready" logic)
- `python.py` - Python REPL and scripts (uses wait channels)
- `ssh.py` - SSH sessions with hover dialog for safety

### Type System

Key types in `types.py`:
- `Target` - Union type for session targets
- `CommandStatus` - Literal types for command status
- `ProcessInfo` - Process detection result
- `ProcessNode` - Process tree node with full info
- `TargetConfig` - Configuration for a target
- `HoverPattern` - Pattern matching for dialogs
- `HoverResult` - Dialog interaction result

### Configuration

`termtap.toml` supports:
- Working directories
- Startup commands
- Environment variables
- Skip processes list (wrappers to ignore)
- Hover patterns (for interactive dialogs)

## Development Workflow

```bash
# Test with debug-bridge
mcp__debug-brdige__terminal_send(session_id="epic-swan", command="uv run python -m termtap")
mcp__debug-brdige__terminal_read(session_id="epic-swan", lines=50)

# MCP server mode
uv run python -m termtap --mcp

# Lint and type check
ruff check packages/termtap --fix
basedpyright packages/termtap
ruff format packages/termtap

# Apply conventions to modules
make conform-module TARGET=packages/termtap/src/termtap/MODULE_NAME
make conform-file TARGET=packages/termtap/src/termtap/FILE.py
```

## Future Enhancements

1. **More Handlers**: Database shells, containers, notebooks
2. **Session Templates**: Pre-configured session types
3. **Process Hooks**: User-defined pre/post command scripts
4. **Better Debugging**: Enhanced process state visibility
5. **Performance**: Lazy loading, connection pooling

## Philosophy

- **Don't recreate what syscalls tell us** - Use /proc and process info
- **Clean over clever** - Simple, direct API usage
- **Extensible not configurable** - Handlers over config options
- **Process-native** - Work with processes, not patterns