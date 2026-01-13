# termtap

Execute commands in tmux panes with intelligent state detection via pattern learning.

## Features

- 🤖 **Pattern Learning** - Teach termtap process states (ready/busy) interactively
- 🎯 **Smart Execution** - Commands wait for processes to be ready before sending
- 🖥️ **Companion UI** - Visual pattern editor and queue management
- 📡 **Daemon Architecture** - Background process with RPC communication
- 🔌 **MCP Support** - Tools and resources for Claude/LLMs
- 📦 **Terminal Emulation** - Precise output capture with tmux streaming

## Prerequisites

Required system dependencies:
- **tmux** - Terminal multiplexer
- **gum** - Interactive terminal UI components (for pattern editing)

```bash
# macOS
brew install tmux gum

# Arch Linux
sudo pacman -S tmux gum

# Ubuntu/Debian
sudo apt install tmux
# For gum: https://github.com/charmbracelet/gum#installation
```

## Installation

```bash
# Install via uv tool (recommended)
uv tool install termtap

# Or with pipx
pipx install termtap

# Update to latest
uv tool upgrade termtap
```

## Quick Start

### 1. Start Daemon
```bash
termtap daemon start
```

### 2. Launch Companion UI (optional but recommended)
```bash
termtap companion
```
The companion provides:
- Pattern editor with live preview
- Queue viewer for pending actions
- Pane selector for interactive workflows

### 3. Run REPL
```bash
termtap
```

### 4. Execute Commands
```python
>>> execute("python3")
# First time: Companion asks if process is ready
# You teach the pattern once, termtap learns it
>>> pane()  # View output
```

## MCP Setup for Claude

```bash
# Quick setup with Claude CLI
claude mcp add termtap -- termtap --mcp

# Or manually edit ~/Library/Application Support/Claude/claude_desktop_config.json:
{
  "mcpServers": {
    "termtap": {
      "command": "termtap",
      "args": ["--mcp"]
    }
  }
}
```

## Commands

| Command | Description |
|---------|-------------|
| `execute(command, target=None)` | Run command in tmux pane, wait for ready state |
| `pane(target=None, offset=0, limit=100)` | Read pane output with pagination |
| `ls(filter=None)` | List tmux sessions |
| `interrupt(target=None)` | Send Ctrl+C to pane |
| `send_keystrokes(keys, target=None)` | Send raw keystrokes (for interactive programs) |
| `debug(code)` | Inspect daemon state (Python expressions) |

## Pattern Learning Workflow

### First Time Execution
```python
>>> execute("python3")
# Companion shows: "Is this process ready? (y/n)"
# You press 'y' and mark the pattern: ">>> "
```

### Pattern Storage
Patterns are saved to `~/.termtap/patterns.json`:
```json
{
  "python": {
    "ready": [">>> ", "\\.\\.\\. "]
  }
}
```

### Subsequent Executions
```python
>>> execute("print('hello')")
# Automatically waits for ">>> " pattern
# Executes immediately when ready
```

## Architecture

### Components

- **Daemon** (`termtap daemon`) - Background process managing pane state
- **Client** - RPC client in REPL/MCP mode
- **Companion** (`termtap companion`) - Textual UI for pattern management
- **Terminal Emulator** - SlimScreen with pyte for output capture

### Action Lifecycle

1. **SELECTING_PANE** - Choose target pane (if not specified)
2. **READY_CHECK** - Check if process matches learned patterns
3. **WATCHING** - Command sent, waiting for completion
4. **COMPLETED** - Process returned to ready state

### Pattern Matching

```
Process Output          Pattern           State
----------------       --------          -------
>>> _                  >>> $             ready
...                    \.\.\. $          ready
Executing...           (any)             busy
```

## Development

```bash
# Clone repository
git clone https://github.com/angelsen/tap-tools
cd tap-tools/packages/termtap

# Install for development
uv sync

# Run checks
basedpyright          # Type checking
ruff check --fix      # Linting

# Run development version
uv run termtap

# Stop daemon
termtap daemon stop
```

## Troubleshooting

### Daemon not responding
```bash
termtap daemon status   # Check daemon state
termtap daemon stop     # Stop daemon
termtap daemon start    # Restart
```

### Pattern not matching
```bash
termtap companion       # Open companion UI
# Navigate to Patterns → Edit pattern → Test with preview
```

### Stuck in READY_CHECK
- Open companion UI
- Queue tab shows pending actions
- Mark pattern as ready/busy or cancel action

## License

MIT - see [LICENSE](../../LICENSE) for details.
