# termtap

Process-native tmux session manager with smart detection and MCP support.

## Features

- **Smart Process Detection** - Shows actual running processes, not just shell names
- **Fuzzy Search** - Filter sessions with `ls("python")` or `ls("demo")`
- **Auto Shell Wrapping** - Automatically wraps non-bash shells for compatibility
- **Service Targets** - Use `demo.backend` notation for multi-service sessions
- **Stream-based Output** - Reliable output capture with metadata tracking
- **MCP Integration** - Use as MCP server for LLM-assisted terminal work

## Quick Start

```python
# Start termtap REPL
uv run termtap

# List all sessions
ls()

# Filter sessions
ls("demo")      # Sessions containing "demo"
ls("python")    # Sessions running python

# Run commands
bash("echo hello", "my-session")

# Read output
read("my-session")

# Manage services
init("demo")    # Create multi-service session
```

## Commands

- `bash(cmd, target)` - Execute command in target pane
- `read(target)` - Read pane output
- `ls(filter)` - List panes with optional filter
- `interrupt(target)` - Send interrupt signal
- `init(name)` - Initialize service group
- `kill(target)` - Kill session/pane

## Architecture

Built on ReplKit2 for dual REPL/MCP functionality. See [PLAN.md](PLAN.md) for design details.