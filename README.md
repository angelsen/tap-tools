# tap-tools

Terminal tools for LLM-assisted debugging and automation.

## 🔧 Tools

### Published on PyPI
- **[tmux-popup](packages/tmux-popup)** - Composable tmux popup system with gum UI components
  ```bash
  uv add tmux-popup  # As library
  ```

- **[termtap](packages/termtap)** - Process-native tmux session manager with MCP support
  ```bash
  uv tool install termtap  # As CLI tool
  pipx install termtap     # Alternative
  ```

### Coming Soon
- **webtap** - Web page inspector for debugging sessions (Private)
- **logtap** - Log stream analyzer and monitor (Private)

## 📋 Prerequisites

```bash
brew install tmux gum            # macOS
sudo pacman -S tmux gum          # Arch
```

## 📦 Quick Start

```bash
# Install termtap
uv tool install termtap

# Add to Claude
claude mcp add termtap -- termtap --mcp

# Run REPL
termtap
```

## 🛠️ Development

This is a UV workspace monorepo. Each tool can be developed and released independently.

```bash
# Clone repository
git clone https://github.com/angelsen/tap-tools
cd tap-tools

# Install dependencies
make sync

# Development commands
make               # Show all commands
make dev-termtap   # Run termtap REPL
make format        # Format code
make lint          # Fix linting issues
make check         # Type check

# Release commands
make check-termtap    # Test build
make release-termtap  # Create release
```

## 📚 Documentation

- [termtap README](packages/termtap/README.md) - Full termtap documentation

## 📄 License

MIT - see [LICENSE](LICENSE) for details.

## 👤 Author

Fredrik Angelsen