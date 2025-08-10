# termtap Architecture

## Overview
Process-native tmux session manager with MCP support. Built on ReplKit2 for dual REPL/MCP functionality, featuring a pane-centric architecture with tmux-native popup interactions.

## Core Design Principles

1. **Pane-Centric**: Everything operates through `Pane` objects with lazy-loaded properties
2. **Process-Native**: Leverage OS-level information from /proc instead of pattern matching
3. **Direct tmux Integration**: Work with tmux's native concepts (panes and popups)
4. **Handler Lifecycle**: Process-specific handlers control execution behavior
5. **Interactive Safety**: Popup confirmations for dangerous operations (SSH, etc.)

## Current Architecture

### Module Structure
```
packages/termtap/src/termtap/
├── __init__.py          # Package exports (app, __version__)
├── __main__.py          # Entry point for python -m termtap
├── app.py               # ReplKit2 app with MCP tools/resources
├── config.py            # Configuration management
├── types.py             # Core type definitions
├── errors.py            # Error response formatters
├── utils.py             # Utility functions (truncate_command, etc.)
├── pane/                # Pane-centric core with optimized execution
│   ├── __init__.py      # Public API exports
│   ├── core.py          # Pure data Pane class with lazy properties
│   ├── execution.py     # Command execution with handler lifecycle
│   ├── inspection.py    # Output reading and process info
│   └── streaming.py     # Stream-based output tracking
├── commands/            # REPL/MCP commands using pane API
│   ├── __init__.py      # Command registration
│   ├── execute.py       # execute() - execute commands with streaming
│   ├── read.py          # read() - MCP resource for output
│   ├── ls.py            # ls() - MCP resource for session list
│   ├── interrupt.py     # interrupt() - send Ctrl+C
│   ├── send_keys.py     # send_keys() - raw keystroke input
│   ├── track.py         # track() - handler development tool
│   └── run.py           # run() - service group management
├── tmux/                # Pure tmux operations (no shell logic)
│   ├── __init__.py      # Public tmux API
│   ├── core.py          # Core tmux operations (run_tmux)
│   ├── resolution.py    # Target resolution logic
│   ├── structure.py     # Session/window/pane creation
│   ├── session.py       # Session management
│   ├── pane.py          # Pane primitives (capture, send_keys)
│   ├── stream.py        # Stream capture via pipes
│   └── names.py         # Docker-style session names
├── process/             # Process detection with pstree algorithm
│   ├── __init__.py      # Process API exports
│   ├── tree.py          # Process tree from /proc/*/stat
│   └── handlers/        # Process-specific handlers
│       ├── __init__.py  # Handler registry and selection
│       ├── default.py   # Default handler
│       ├── python.py    # Python REPL detection
│       ├── ssh.py       # SSH with popup confirmations
│       └── claude.py    # Claude-specific handling
├── popup/               # Tmux-native popup system with gum
│   ├── __init__.py      # Popup API exports
│   ├── builder.py       # Popup builder with theme support
│   ├── examples.py      # Usage examples
│   └── llms.txt         # LLM documentation
└── filters.py           # Output filtering functions
```

### Key Architecture Features

1. **Pane-Centric Core**: All operations through `Pane` objects with lazy-loaded properties
2. **Unified Streaming**: Single handler-controlled interface for output capture
3. **Popup System**: Tmux-native popups using gum for rich terminal UIs
4. **Handler Lifecycle**: Process-specific handlers with before/after hooks
5. **Performance**: Optimized process scanning with minimal syscalls

### Command Patterns

Each command uses the pane-centric API:
```python
@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"}
)
def execute(state, command: str, target: Target = "default"):
    """Execute command in target pane."""
    try:
        pane_id, session_window_pane = resolve_or_create_target(target)
    except RuntimeError as e:
        return {"elements": [{"type": "text", "content": f"Error: {e}"}], 
                "frontmatter": {"status": "error"}}
    
    pane = Pane(pane_id)
    result = send_command(pane, command, wait=True)
    
    # Format result for markdown display
    return {"elements": [...], "frontmatter": {"status": result["status"]}}
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

# Run linting and type checking
ruff check packages/termtap/ --fix
basedpyright packages/termtap/

# Test with ReplKit2 Termtap
mcp__termtap-dev__bash(command="uv run termtap")
help()  # In REPL for command list
```

## Recent Improvements

1. **Pane-Centric Refactor**: Optimized execution with lazy-loaded properties
2. **Popup System**: Tmux-native popups with gum for interactive confirmations
3. **Unified Streaming**: Handler-controlled output capture with command IDs
4. **SSH Safety**: Interactive command editing before remote execution
5. **Issue Tracking**: Comprehensive documentation in `/docs/issues/`

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