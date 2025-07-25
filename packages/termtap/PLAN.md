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
├── app.py               # ReplKit2 app with minimal commands
├── config.py            # Configuration with skip_processes support
├── types.py             # Type definitions (Target, CommandStatus, etc.)
├── core/
│   ├── control.py       # Process control (interrupt, signal, kill)
│   └── execute.py       # Command execution with streaming
├── tmux/
│   ├── session.py       # Session management
│   ├── pane.py          # Pane capture functions  
│   ├── stream.py        # Streaming sidecar for output
│   └── utils.py         # Low-level tmux operations
├── process/
│   ├── detector.py      # Process state detection
│   ├── tree.py          # Process tree analysis
│   └── handlers/        # Pluggable handlers per process type
└── hover/               # Interactive dialogs (used by handlers)
```

### Key APIs

#### app.py - Essential Commands
- `bash(command, target, wait, timeout)` - Execute with streaming output
- `read(target, lines)` - Direct tmux capture
- `ls()` - List sessions with process info
- `active()` - Show only working processes
- `interrupt(session)` - Send Ctrl+C

#### tmux Module - Public API
- `list_sessions()` - Get all sessions
- `session_exists()`, `get_or_create_session()`, `kill_session()`
- `capture_visible()`, `capture_all()`, `capture_last_n()`
- `get_pane_pid()`, `get_pane_for_session()`
- `send_keys()` - Send keystrokes

#### process Module - Public API
- `is_ready(session)` - Check if ready for input
- `wait_until_ready(session, timeout)` - Wait for readiness
- `get_process_info(session)` - Debug information

#### core Module - Public API
- `execute(state, command, target, wait, timeout)` - Main execution
- `send_interrupt()`, `send_signal()`, `kill_process()`
- `ExecutorState` - Just holds StreamManager

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
- `default.py` - Generic processes
- `claude.py` - Claude/AI assistants
- `ssh.py` - SSH sessions with safety checks

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

# Or run directly
uv run python -m termtap          # REPL mode
uv run python -m termtap --mcp    # MCP server mode
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