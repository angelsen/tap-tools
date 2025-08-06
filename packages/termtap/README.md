# termtap

Process-native tmux session manager with pane-centric architecture and MCP support.

## Features

- **Pane-Centric Architecture** - Everything operates through `Pane` objects with lazy-loaded properties
- **Smart Process Detection** - Shows actual running processes using pstree algorithm
- **Service Orchestration** - Run multi-service environments with dependency management
- **Ready Pattern Support** - Detect service startup with custom regex patterns
- **Fuzzy Search** - Filter sessions with `ls("python")` or `ls("demo")`
- **Auto Shell Wrapping** - Automatically wraps non-bash shells for compatibility
- **Service Targets** - Use `demo.backend` notation for multi-service sessions
- **MCP Integration** - Use as MCP server for LLM-assisted terminal work
- **70% Performance Improvement** - Optimized execution with minimal process scans

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

# Read output
read("my-session")

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

- `bash(cmd, target)` - Execute command in target pane
- `read(target, lines=50)` - Read pane output with optional line limit
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

## Performance

The pane-centric refactor delivers significant performance improvements:
- Average execution: **388ms** (down from 1300ms)
- Process scan optimization: 2-3 scans per command (down from 10+)
- Unified execution path reduces overhead

## Architecture

Built on ReplKit2 for dual REPL/MCP functionality. The pane module provides:
- **pane/core.py** - Pure data `Pane` class with lazy properties
- **pane/execution.py** - Command execution with handler lifecycle
- **pane/inspection.py** - Output reading and process info
- **pane/streaming.py** - Stream-based output tracking

Process detection uses pstree algorithm for accurate child tracking, with specialized handlers for different process types (Python, SSH, Claude, etc).