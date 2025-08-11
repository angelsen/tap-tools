# tmux-popup

Composable tmux popup system with gum UI components.

<p align="center">
  <img src="https://github.com/angelsen/tap-tools/blob/main/assets/recordings/processed/tmux-popup-demo.gif" width="640" alt="tmux-popup demo">
  <br>
  <em>Interactive popup components in action</em>
</p>

## ✨ Features

- 🎨 **Rich Components** - Styled text, inputs, selections, confirmations
- 🔧 **Composable API** - Chain commands for complex interactions
- 📦 **Zero Dependencies** - Pure Python, only needs tmux and gum
- 🎯 **Type-Safe** - Full type hints and result parsing
- 🚀 **Lightweight** - Simple, focused library

## 📋 Prerequisites

Required system tools:
- **tmux** - Terminal multiplexer for popups
- **gum** - Provides the UI components

```bash
# macOS
brew install tmux gum

# Arch Linux
sudo pacman -S tmux gum

# Ubuntu/Debian
sudo apt install tmux
# For gum: https://github.com/charmbracelet/gum#installation
```

## 📦 Installation

```bash
# Install from PyPI (coming soon)
uv add tmux-popup                  # Recommended
pip install tmux-popup             # Alternative

# Install from source
uv add git+https://github.com/angelsen/tap-tools.git#subdirectory=packages/tmux-popup
# Or with pip:
pip install git+https://github.com/angelsen/tap-tools.git#subdirectory=packages/tmux-popup
```

## 🚀 Quick Start

```python
from tmux_popup import Popup
from tmux_popup.gum import GumStyle, GumInput, GumChoose

# Create a simple popup
popup = Popup(width="65", title="My App")
result = popup.add(
    GumStyle("Welcome!", header=True),
    GumInput(placeholder="Enter your name...")
).show()

print(f"Hello, {result}!")
```

## 🎮 Usage

### Basic Input
```python
popup = Popup(width="50")
name = popup.add(
    GumStyle("User Setup", header=True),
    "Please enter your details:",
    GumInput(placeholder="Name...", value="")
).show()
```

### Confirmations
```python
popup = Popup()
confirmed = popup.add(
    GumStyle("⚠️ Warning", warning=True),
    "This will delete all data.",
    GumConfirm("Are you sure?", default=False)
).show()

if confirmed:
    # Proceed with deletion
    pass
```

### Selections
```python
# Single choice
choice = popup.add(
    GumStyle("Select Action", header=True),
    GumChoose([
        ("new", "📝 New File"),
        ("open", "📂 Open File"),
        ("save", "💾 Save File"),
        ("quit", "❌ Quit")
    ])
).show()

# Multiple selection with fuzzy search
items = ["Python", "JavaScript", "Go", "Rust", "TypeScript"]
selected = popup.add(
    GumStyle("Select Languages", info=True),
    GumFilter(items, limit=0, fuzzy=True)
).show()  # Returns list of selected items
```

### Tables
```python
data = [
    ["Active", "Server 1", "192.168.1.10"],
    ["Idle", "Server 2", "192.168.1.11"],
    ["Active", "Server 3", "192.168.1.12"],
]

selected_ip = popup.add(
    GumStyle("Select Server", header=True),
    GumTable(
        data,
        headers=["Status", "Name", "IP"],
        return_column=2  # Return IP column
    )
).show()
```

## 📚 Components

### Core
- `Popup` - Main popup runner with tmux display-popup
- `Command` - Base class for all UI commands

### Input Components
- `GumInput` - Single line text input
- `GumWrite` - Multi-line text editor
- `GumConfirm` - Yes/no confirmation

### Selection Components
- `GumChoose` - Single choice from list
- `GumFilter` - Fuzzy search with multi-select
- `GumFile` - File picker
- `GumTable` - Table with row selection

### Display Components
- `GumStyle` - Styled text with presets (header, info, warning, error)
- `GumFormat` - Markdown/template formatting
- `GumPager` - Scrollable text viewer
- `GumLog` - Formatted log display

### Utility Components
- `GumJoin` - Layout multiple elements
- `GumSpin` - Loading spinner for async operations

## 🏗️ Architecture

The library follows a simple pattern:
1. **Commands** render themselves to shell script
2. **Popup** combines commands and executes via tmux
3. **Results** are parsed and returned to Python

```python
# Commands know how to render
cmd = GumInput(value="default")
script_lines = cmd.render()  # Returns list of shell commands

# Popup handles execution
popup = Popup()
result = popup.add(cmd).show()  # Executes and returns parsed result
```

## 🛠️ Development

```bash
# Clone repository
git clone https://github.com/angelsen/tap-tools
cd tap-tools

# Install for development (recommended)
uv sync
uv run --package tmux-popup python examples/demo.py

# Or with pip:
cd packages/tmux-popup
pip install -e .
python examples/demo.py
```

## 📄 License

MIT - see [LICENSE](../../LICENSE) for details.

## 👤 Author

Fredrik Angelsen

## 🙏 Acknowledgments

Built on top of:
- [tmux](https://github.com/tmux/tmux) - Terminal multiplexer
- [gum](https://github.com/charmbracelet/gum) - Delightful CLI interactions