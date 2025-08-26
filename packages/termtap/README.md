# termtap

Process-native tmux session manager with MCP support.

## ✨ Features

- 🎯 **Smart Detection** - Auto-detects Python, SSH, Claude processes
- 📝 **Handler System** - Process-specific output filtering and caching
- 🔌 **MCP Ready** - Tools and resources for Claude/LLMs
- 🚀 **Service Orchestration** - Run multi-service environments
- 🔍 **Fuzzy Search** - Filter sessions with patterns
- 🎨 **Rich Display** - Tables, boxes, and formatted output

## 📋 Prerequisites

Required system dependencies:
- **tmux** - Terminal multiplexer
- **gum** - Interactive terminal UI components

```bash
# macOS
brew install tmux gum

# Arch Linux
sudo pacman -S tmux gum

# Ubuntu/Debian
sudo apt install tmux
# For gum, see: https://github.com/charmbracelet/gum#installation

# Fedora
sudo dnf install tmux
# For gum, use: go install github.com/charmbracelet/gum@latest
```

## 📦 Installation

```bash
# Install via uv tool (recommended)
uv tool install termtap

# Or with pipx
pipx install termtap

# Update to latest
uv tool upgrade termtap

# Uninstall
uv tool uninstall termtap
```

## 🚀 Quick Start

```bash
# 1. Install termtap
uv tool install "git+https://github.com/angelsen/tap-tools.git#subdirectory=packages/termtap"

# 2. Add to Claude
claude mcp add termtap -- termtap --mcp

# 3. Run REPL
termtap
```

## 🔌 MCP Setup for Claude

```bash
# Quick setup with Claude CLI
claude mcp add termtap -- termtap --mcp
```

Or manually configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "termtap": {
      "command": "termtap",
      "args": ["--mcp"]
    }
  }
}
```

## 🎮 Usage

### Interactive REPL
```bash
termtap                     # Start REPL
termtap --mcp               # Start as MCP server
```

### Commands
```python
>>> ls()                    # List all sessions with processes
>>> execute("python3")      # Start Python REPL in tmux
>>> pane()                  # Read output with caching and interaction hints
>>> interrupt()             # Send Ctrl+C to current pane
>>> run("demo")             # Run service group from config
```

### Command Reference

| Command | Description |
|---------|------------|
| `execute(command, target=None)` | Run command in tmux pane |
| `pane(target=None, page=None)` | Read output with pagination and interaction hints |
| `ls(filter=None)` | List sessions with optional filter |
| `interrupt(target=None)` | Send interrupt signal |
| `send_keys(keys, target=None)` | Send raw key sequences |
| `run(group)` | Run service configuration |
| `track(target=None, duration=10)` | Monitor pane state |

## 🛠️ Service Configuration

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

Run with: `run("demo")`

## 📁 Examples

See `examples/` directory for:
- Basic usage patterns
- Service orchestration setups
- MCP integration examples

## 🏗️ Architecture

Built on [ReplKit2](https://github.com/angelsen/replkit2) for dual REPL/MCP functionality.

**Key Design:**
- **Pane-Centric** - Everything operates through `Pane` objects
- **Process-Native** - Uses `/proc` and tmux state directly
- **Handler System** - Process-specific capture and filtering
- **0-Based Pagination** - Navigate cached output efficiently

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design
- [Handlers](src/termtap/process/handlers/) - Process-specific handlers
- [Commands](src/termtap/commands/) - Command implementations

## 🛠️ Development

```bash
# Clone repository
git clone https://github.com/angelsen/tap-tools
cd tap-tools

# Install for development
uv sync --package termtap

# Run development version
uv run --package termtap termtap

# Run tests and checks
make check-termtap  # Check build
make format         # Format code
make lint           # Fix linting
```

## 📄 License

MIT - see [LICENSE](../../LICENSE) for details.