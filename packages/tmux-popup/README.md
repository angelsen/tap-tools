# tmux-popup

Composable tmux popup system with gum UI components.

<p align="center">
  <img src="https://raw.githubusercontent.com/angelsen/tap-tools/main/assets/recordings/processed/tmux-popup-demo.gif" width="640" alt="tmux-popup demo">
</p>

## Features

🎨 **Rich Display** - Canvas with Markdown and flexible layouts  
🔧 **Hybrid Approach** - Python data handling + full gum passthrough  
📦 **Zero Dependencies** - Pure Python, only needs tmux and gum  
🎯 **Type-Safe** - Full type hints with proper base classes  
🔍 **Fuzzy Search** - Multi-select filtering with dict support

## Installation

```bash
# Prerequisites
sudo pacman -S tmux gum       # Arch
brew install tmux gum         # macOS

# Install package
uv add tmux-popup             # Recommended
pip install tmux-popup        # Alternative
```

## Quick Start

```python
from tmux_popup import Popup, Canvas, Text, Input, Choose

# Display text
popup = Popup(width="60%", height="30%")
canvas = Canvas(border="rounded", padding="1")
canvas.add(Text("Welcome to tmux-popup!"))
popup.add(canvas).show()

# Get input
name = Popup().add(Input(prompt="Name: ")).show()

# Display then choose
popup = Popup()
popup.add(Canvas().add(Text("Continue?")))
result = popup.add(Choose(options=["Yes", "No"])).show()
```

## Core Concepts

### Three Patterns

```python
# 1. Display only
Popup().add(Canvas().add(content)).show()

# 2. Input only  
Popup().add(interactive_element).show()

# 3. Display + Input
popup = Popup()
popup.add(Canvas().add(content))
result = popup.add(interactive_element).show()
```

### Content & Layout

```python
from tmux_popup import Popup, Canvas, Markdown, Text, Row, Column

# Rich content with Markdown
canvas = Canvas(border="rounded", padding="1")
canvas.add(Markdown("""# Title

**Bold**, *italic*, `code`

\```python
def hello():
    print("Hi!")
\```
"""))

# Two-column layout
left = Column(width="50%", border="normal", padding="1")
left.add(Markdown("## Left"))

right = Column(width="50%", border="normal", padding="1")  
right.add(Text("Right content"))

canvas.add(Row(left, right))
popup.add(canvas).show()
```

### Interactive Elements

```python
from tmux_popup import Input, Choose, Filter, Confirm, Table

# Text input
email = Popup().add(
    Input(prompt="Email: ", placeholder="user@example.com")
).show()

# Single choice (dict shows labels, returns values)
actions = {
    "📝 New File": "new",
    "📂 Open": "open",
    "❌ Quit": "quit"
}
result = Popup().add(Choose(options=actions)).show()  # Returns: "new", "open", or "quit"

# Multi-select with fuzzy search
packages = ["numpy", "pandas", "fastapi", "django"]
selected = Popup().add(
    Filter(options=packages, no_limit=True, fuzzy=True)
).show()  # Returns: ["numpy", "pandas"]

# Confirmation
if Popup().add(Confirm(prompt="Delete all?")).show():
    print("Deleting...")

# Table selection
data = [
    {"name": "Alice", "role": "Admin"},
    {"name": "Bob", "role": "User"}
]
row = Popup().add(Table(data=data)).show()  # Returns selected row dict
```

## Advanced Features

### Complete Example

```python
from tmux_popup import Popup, Canvas, Row, Column, Markdown, Text, Filter

# Build interface
popup = Popup(width="80%", height="60%")
canvas = Canvas(border="rounded", padding="1")

# Two columns
left = Column(width="50%", padding="1")
left.add(Markdown("## Instructions\n\n• Type to filter\n• Space to select"))

right = Column(width="50%", padding="1")
right.add(Markdown("## Example\n\n    packages = ['numpy', 'pandas']"))

canvas.add(Row(left, right))
popup.add(canvas)

# Add interactive filter
packages = {"NumPy": "numpy", "Pandas": "pandas"}
selected = popup.add(
    Filter(options=packages, no_limit=True, fuzzy=True)
).show()
```

### Gum Passthrough

All gum flags work via kwargs:

```python
Choose(
    options=["A", "B", "C"],
    cursor_foreground="212",   # gum styling
    height=10,                 # gum display option
    select_if_one=True,        # gum behavior
    header="Select:"           # gum text
)
```

### Debug Mode

```python
# See generated shell script
Popup(debug=True).add(Canvas().add("Test")).show()
```

## Components Reference

**Core**
- `Popup` - Main container (width, height, border, debug)
- `Canvas` - Content area (border, padding, margin, align)

**Content** 
- `Text` - Plain text
- `Markdown` - Formatted markdown with code blocks

**Layout**
- `Row` - Horizontal container
- `Column` - Vertical container (width, border, padding)

**Interactive**
- `Input` - Single-line input (prompt, placeholder, header)
- `Write` - Multi-line editor (width, height)
- `Confirm` - Yes/no dialog (prompt, affirmative, negative)
- `Choose` - Single/multi selection (options, limit, header)
- `Filter` - Fuzzy search (options, no_limit, fuzzy)
- `Table` - Tabular selection (data, border)
- `FilePicker` - File browser (path, file, all)
- `Pager` - Scrollable viewer (content)
- `Spin` - Loading spinner (command, title)
- `Format` - Text formatter (content, format_type)

**Types**
- `TimeoutResult`, `CancelledResult` - Special return values

## Development

```bash
git clone https://github.com/angelsen/tap-tools
cd tap-tools/packages/tmux-popup
uv sync

# Run examples
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