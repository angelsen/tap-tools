# termtap Architecture

## Core Design Principles

**Process-Native**: Don't recreate what the OS already knows.
- Use `/proc` for process information
- Query tmux state directly (no shadow state)
- First non-shell process for meaningful display

**Pane-Centric**: Everything operates through `Pane` objects.
- Lazy-loaded properties for efficiency
- Unified execution path
- Consistent return formats

**Handler-Centric Caching**: Process handlers own output management.
- Process-specific filtering (SSH aggressive, Python minimal)
- Centralized caching logic
- ~30-40% code reduction in commands

## Module Structure

```
termtap/
├── pane/               # Pane abstraction (core)
│   ├── core.py        # Pane class with lazy properties
│   ├── execution.py   # Command execution with handler lifecycle
│   └── inspection.py  # Output reading and process info
│
├── process/           # Process detection and handling
│   ├── tree.py       # pstree algorithm using /proc
│   └── handlers/     # Process-specific handlers
│       ├── __init__.py    # Handler registry and base class
│       ├── python.py      # Python REPL handler
│       ├── ssh.py         # SSH session handler
│       └── claude.py      # Claude CLI handler
│
├── tmux/              # Pure tmux operations
│   ├── core.py       # Basic tmux commands
│   ├── session.py    # Session management
│   └── stream.py     # Output streaming
│
├── commands/          # REPL/MCP commands
│   ├── execute.py    # Run commands in panes
│   ├── read.py       # Read output with caching
│   └── interrupt.py  # Send signals
│
└── app.py            # ReplKit2 app definition
```

## Key Flows

### Command Execution
```python
execute(command, target) 
  → resolve_pane(target)
  → get_handler(pane)
  → handler.before_send(command)
  → send_command(pane, command)
  → handler.capture_output(pane, state)
```

### Process Detection
```python
Pane(pane_id)
  → get_process_tree()     # From /proc
  → find_first_non_shell()  # Skip bash/zsh
  → get_handler()          # Match handler
```

### Output Caching
```python
read(target, page)
  → get_handler(pane)
  → handler.capture_output(pane, state)  # Uses cache
  → paginate(output, page)               # 0-based pages
```

## Handler System

Each handler implements:
- `can_handle(pane)` - Process detection
- `is_ready(pane)` - State detection (ready/busy/unknown)
- `capture_output(pane, state)` - Caching and filtering
- `before_send(pane, command)` - Command preprocessing

### Handler Selection
1. Check active process name
2. Match against handler's `_handles` list
3. Fall back to DefaultHandler

### Cache Strategy
- Commands use stream capture (partial output)
- Reads use full buffer capture
- Cache stored in handler state dict
- Pages are 0-based with negative indexing

## Dependencies

Built on [ReplKit2](https://github.com/angelsen/replkit2):
- Dual REPL/MCP functionality
- Rich display formatting
- State management
- MCP protocol support