# termtap

Process-native tmux session manager with MCP support.

## Features

- **Pane-Centric Architecture** - Everything operates through `Pane` objects with lazy-loaded properties
- **Smart Process Detection** - Shows actual running processes using pstree algorithm
- **Handler-Centric Output** - Process-specific capture, filtering, and caching
- **Service Orchestration** - Run multi-service environments with dependency management
- **Ready Pattern Support** - Detect service startup with custom regex patterns
- **Fuzzy Search** - Filter sessions with `ls("python")` or `ls("demo")`
- **Auto Shell Wrapping** - Automatically wraps non-bash shells for compatibility
- **Service Targets** - Use `demo.backend` notation for multi-service sessions
- **MCP Integration** - Use as MCP server for LLM-assisted terminal work
- **0-Based Pagination** - Navigate cached output with `read(target, page=0)`

## Quick Start

```python
# Start termtap REPL
uv run termtap

# List all sessions with process info
ls()

# Filter sessions
ls("demo")      # Sessions containing "demo"
ls("python")    # Sessions running python

# Run commands
bash("echo hello", "my-session")

# Read output (fresh capture)
read("my-session")

# Read from cache (0=most recent, 1=older, -1=oldest)
read("my-session", page=0)

# Send raw keys
send_keys("my-session", "Up", "Enter")

# Interrupt a process
interrupt("my-session")

# Run development environment
run("demo")  # Starts services from termtap.toml

# Kill session
kill("my-session")
```

## Commands

- `bash(cmd, target)` - Execute command in target pane with output caching
- `read(target, page=None)` - Read pane output (None=fresh, 0+=cached pages)
- `ls(filter)` - List panes with process info and optional filter
- `interrupt(target)` - Send interrupt signal (Ctrl+C)
- `send_keys(target, *keys, enter=False)` - Send raw key sequences
- `run(group)` - Run service group from configuration
- `run_list()` - List available service configurations
- `kill(target)` - Kill session or pane
- `track(target)` - Monitor pane state and handler detection

## Pane-Centric Architecture

All operations in termtap work through the `Pane` abstraction:

```python
from termtap.pane import Pane, send_command

# Create pane object
pane = Pane("%42")  # Using tmux pane ID

# Access properties (lazy-loaded)
pane.session_window_pane  # "demo:0.1"
pane.pid                  # 12345
pane.process             # First non-shell process
pane.shell               # Shell process
pane.visible_content     # Current pane content
pane.handler             # Process-specific handler

# Execute commands
result = send_command(pane, "echo hello")
# Returns: {
#   "status": "completed",
#   "output": "hello",
#   "elapsed": 0.388,
#   "process": "bash",
#   ...
# }
```

## Service Configuration

Define multi-service environments in `termtap.toml`:

```toml
[init.demo]
layout = "even-horizontal"

[init.demo.backend]
pane = 0
command = "uv run python -m backend"
path = "demo/backend"
ready_pattern = "Uvicorn running on"
timeout = 10

[init.demo.frontend]
pane = 1  
command = "npm run dev"
path = "demo/frontend"
ready_pattern = "Local:.*localhost"
depends_on = ["backend"]
```

## Handler System

Process-specific handlers provide intelligent output management:
- **Capture Methods** - Stream for commands, full buffer for reads
- **Smart Filtering** - SSH aggressive filtering, Python minimal filtering
- **Automatic Caching** - Handler caches full output, returns display subset
- **Process Detection** - Handlers selected based on running process

## Architecture

Built on ReplKit2 for dual REPL/MCP functionality:

**Core Modules:**
- `pane/` - Pane abstraction with lazy properties and execution
- `process/handlers/` - Process-specific capture and filtering
- `tmux/` - Pure tmux operations and stream management
- `commands/` - REPL/MCP command implementations

**Key Design:**
- Process detection uses pstree algorithm for accurate child tracking
- Handlers centralize all output capture, filtering, and caching logic
- Commands orchestrate while handlers execute
- 0-based pagination with Python-style negative indexing