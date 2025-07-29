# termtap Architecture

## Overview
Process-native tmux session manager with MCP support. Built on ReplKit2 for dual REPL/MCP functionality, emphasizing simplicity and direct tmux integration.

## Core Design Principles

1. **Process-Native**: Leverage OS-level information from /proc instead of pattern matching
2. **Command Ownership**: Each command owns its complete workflow - no hidden orchestration
3. **Direct tmux Integration**: Work with tmux's native concepts (panes, not sessions)
4. **Minimal Abstractions**: Only create types for unique identifiers, config, and API contracts
5. **Error Transparency**: Clear error messages without hiding implementation details

## Current Architecture

### Module Structure
```
packages/termtap/src/termtap/
├── __init__.py          # Package exports (app, __version__)
├── __main__.py          # Entry point for python -m termtap
├── app.py               # ReplKit2 app with commands
├── config.py            # Configuration management
├── types.py             # Core type definitions
├── errors.py            # Error response formatters
├── commands/            # Command implementations (each owns its workflow)
│   ├── __init__.py      # Exports command registration
│   ├── bash.py          # bash() command with full workflow
│   ├── read.py          # read() command implementation
│   ├── ls.py            # ls() command with fuzzy filtering
│   ├── interrupt.py     # interrupt() command
│   └── init.py          # init(), init_list(), kill() commands
├── tmux/                # Pure tmux operations
│   ├── __init__.py      # Exports all public tmux functions
│   ├── core.py          # Core tmux operations (run_tmux, get_pane_id)
│   ├── resolution.py    # Target resolution logic
│   ├── structure.py     # Complex session/window/pane creation
│   ├── session.py       # Session management
│   ├── pane.py          # Pane operations and PaneInfo
│   ├── stream.py        # Stream-based output capture
│   ├── names.py         # Session name generation
│   └── exceptions.py    # TmuxError, PaneNotFoundError, CurrentPaneError
├── process/             # Process detection
│   ├── __init__.py      # Exports process detection functions
│   ├── detector.py      # Process state detection
│   ├── tree.py          # Process tree analysis using /proc
│   └── handlers/        # Process-specific handlers
│       ├── __init__.py  # Handler registry and base class
│       ├── default.py   # Default handler (no children = ready)
│       ├── python.py    # Python REPL/script detection
│       └── ssh.py       # SSH session safety
└── hover/               # Interactive dialogs
    ├── __init__.py      # Hover dialog interface
    └── dialog.sh        # Shell script for UI
```

### Key Design Changes (Post-Refactor)

1. **Pane-First Architecture**: All operations work with pane IDs, not session names
2. **Command Independence**: Each command in `commands/` handles its complete workflow
3. **No CommandResult Type**: Commands return what makes sense for their display type
4. **Direct Markdown**: Commands return markdown dicts directly, no formatter indirection
5. **Simplified Error Handling**: Consistent error patterns without complex hierarchies

### Command Patterns

Each command follows a simple pattern:
```python
@app.command(display="markdown")  # or "table", etc.
def command_name(state, arg1: str, arg2: Optional[int] = None):
    """Docstring becomes help text."""
    try:
        # Resolve targets
        # Perform operations
        # Return display-appropriate data
    except SpecificError as e:
        # Return user-friendly error
        return markdown_error_response(str(e))
```

### Error Handling Architecture

- **Modules raise**: Descriptive RuntimeError or domain exceptions
- **Commands catch**: Transform to user-friendly messages
- **No raw tracebacks**: All errors are formatted for users
- **Consistent format**: `{"elements": [...], "frontmatter": {"status": "error"}}`

### Target Resolution

Supports multiple target formats:
- **Pane ID**: `%42` - Direct tmux pane reference
- **Session:Window.Pane**: `demo:0.0` - Full specification
- **Session**: `demo` - May resolve to multiple panes
- **Service**: `demo.backend` - Resolves via config

### Process Detection

Uses pstree algorithm scanning `/proc/*/stat`:
- Builds complete process tree from PPID relationships
- Selects first non-shell process for display
- Returns sensible defaults on failure
- No exceptions for non-critical operations

## Testing & Development

```bash
# Run termtap REPL
uv run termtap

# Run tests
ruff check packages/termtap/ --fix
basedpyright packages/termtap/

# Test with debug-bridge
mcp__debug-brdige__terminal_send(session_id="epic-swan", command="uv run termtap")
```

## Recent Improvements

1. **Unified Error Handling**: All commands follow ERROR_HANDLING_SPEC.md
2. **Type Safety**: Full basedpyright compliance with proper Optional handling
3. **Fuzzy ls()**: Added filter parameter for flexible session/process search
4. **Domain Exceptions**: Added PaneNotFoundError, WindowNotFoundError
5. **Cleaner Architecture**: Removed complex orchestration in favor of direct command ownership

## Future Considerations

1. **More Handlers**: Container, database, notebook process handlers
2. **Better Process Info**: Enhanced metadata from /proc
3. **Session Templates**: Pre-configured multi-service setups
4. **Performance**: Batch operations for large session counts
5. **Testing**: Comprehensive test suite for error paths

## Philosophy

- **Simplicity over cleverness**: Direct, obvious implementations
- **User experience first**: Clear errors, helpful messages
- **Leverage the OS**: Use /proc, tmux state, system tools
- **Fail gracefully**: Return defaults, not exceptions
- **Progressive disclosure**: Simple commands, powerful options