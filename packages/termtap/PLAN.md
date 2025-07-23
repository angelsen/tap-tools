# termtap Implementation Plan

## Overview
Minimal tmux-based terminal session manager built with ReplKit2. Commands work natively in REPL and automatically expose as MCP tools/resources via FastMCP decorators.

## Core Design Principles
1. **ReplKit2-native**: Commands are REPL-first, MCP-second
2. **tmux as state**: tmux sessions ARE the state
3. **Test with debug-bridge**: Use terminal_send/read for development
4. **Config optional**: Works with zero config, enhanced by termtap.toml

## Architecture

### Module Structure
```
packages/termtap/src/termtap/
├── __init__.py          # App setup, exports
├── __main__.py          # CLI entry point (--mcp flag)
├── app.py               # ReplKit2 App definition
├── config.py            # termtap.toml parsing
└── tmux/
    ├── __init__.py      # Public tmux API
    ├── session.py       # Session management
    ├── capture.py       # Output capture
    └── utils.py         # Helpers (escape, parse)
```

### ReplKit2 App Definition

```python
from replkit2 import App
from dataclasses import dataclass

@dataclass
class TermTapState:
    config: dict = None
    
    @property
    def sessions(self):
        # Live view into tmux
        return tmux.list_sessions()

app = App(
    "termtap",
    TermTapState,
    uri_scheme="bash",  # bash:// URIs
    fastmcp={"tags": {"terminal", "automation"}}
)
```

### Commands (REPL + MCP)

```python
# MCP Tool: Execute command in session
@app.command(display="box", fastmcp={"type": "tool"})
def bash(state, command: str, target: str = "default", wait: bool = True, timeout: int = 30000):
    """Execute command in target session."""
    # Works in REPL: termtap> bash "ls -la" frontend
    # Works in MCP: mcp__termtap__bash(command="ls -la", target="frontend")
    session = get_or_create_session(state, target)
    return tmux.send_command(session, command, wait, timeout)

# MCP Resource: Read session output
@app.command(display="text", fastmcp={"type": "resource"})
def read(state, target: str = "default", lines: int = None):
    """Read output from target session."""
    # REPL: termtap> read frontend 30
    # MCP: bash://frontend/30
    # URI template: bash://{target}/{lines}
    return tmux.capture_pane(f"termtap-{target}", lines)

# REPL-only: Interactive commands
@app.command(display="table", headers=["Session", "Created", "Attached"], fastmcp={"enabled": False})
def list(state):
    """List all termtap sessions."""
    return [{"Session": s.name, "Created": s.created, "Attached": s.attached} 
            for s in state.sessions]

@app.command(fastmcp={"enabled": False})
def attach(state, target: str):
    """Attach to session in current terminal."""
    os.system(f"tmux attach -t termtap-{target}")

@app.command(fastmcp={"enabled": False})
def join(state, target: str):
    """Join session as pane in current tmux."""
    os.system(f"tmux join-pane -s termtap-{target}")
```

### Config Format (termtap.toml)
```toml
[default]
# Runs in current directory if no config

[frontend]
dir = "./frontend"
start = "npm run dev"  # Optional auto-start command

[backend]
dir = "./backend"
env = { PYTHONPATH = "." }
```

## Development Workflow

### 1. Build with debug-bridge
```python
# Start debug-bridge terminal session
mcp__debug-bridge__terminal_start(command="python", session_id="termtap-dev")

# Test termtap in REPL mode
mcp__debug-bridge__terminal_send(
    session_id="termtap-dev",
    command="uv run python -m termtap"
)

# Test commands interactively
mcp__debug-bridge__terminal_send(
    session_id="termtap-dev", 
    command='bash "echo hello" frontend'
)
```

### 2. Test MCP Mode
```bash
# Run MCP server
uv run python -m termtap --mcp

# Commands automatically available as:
# - mcp__termtap__bash
# - Resource: bash://target/lines
```

## Implementation Steps

### Phase 1: Core tmux Module
1. Create minimal tmux wrapper using subprocess
2. Test with simple scripts before ReplKit2 integration
3. Ensure proper command escaping and output capture

### Phase 2: ReplKit2 App
1. Define TermTapState with live tmux view
2. Create bash command (REPL + MCP tool)
3. Create read command (REPL + MCP resource)
4. Add REPL-only commands (list, attach, join)

### Phase 3: Config & Polish
1. Add termtap.toml parsing
2. Auto-start sessions from config
3. Handle missing tmux gracefully
4. Add helpful display formatting

## Key Implementation Details

### Session Naming
- Config targets: `termtap-{target}`
- Prevents collision with user sessions
- Easy to identify in tmux list

### Command Testing in REPL
```
termtap> bash "pwd"
/home/user/project

termtap> bash "npm run dev" frontend
Starting frontend dev server...

termtap> read frontend 10
[last 10 lines of frontend output]

termtap> list
Session            Created    Attached
termtap-default    10:23      No
termtap-frontend   10:24      No
```

### URI Resolution
- `bash://` → list all sessions
- `bash://frontend` → read(target="frontend")
- `bash://frontend/30` → read(target="frontend", lines=30)

## Success Criteria
1. Commands work identically in REPL and MCP
2. Can develop/test entirely using debug-bridge terminal
3. Zero-config usage works immediately
4. tmux sessions visible and joinable
5. Clean ReplKit2 patterns throughout