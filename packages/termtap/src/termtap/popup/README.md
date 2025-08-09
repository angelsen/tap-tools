# Popup System

Composable tmux popup system with gum-based UI components.

## Architecture

```python
from termtap.popup import Popup
from termtap.popup.gum import GumStyle, GumInput, GumChoose

popup = Popup(width="65", title="My Popup")
result = popup.add(
    GumStyle("Header", header=True),
    GumStyle("Info message", info=True),
    "",  # Spacer
    GumInput(placeholder="Enter value...", value="default")
).show()
```

## Components

### Core
- `Popup` - Tmux display-popup runner
- `Command` - Base class for all commands

### Gum Commands
- **Selection**: `GumChoose`, `GumFilter`, `GumFile`, `GumTable`
- **Input**: `GumInput`, `GumWrite`, `GumConfirm`
- **Display**: `GumStyle`, `GumFormat`, `GumLog`, `GumPager`
- **Layout**: `GumJoin`
- **Process**: `GumSpin`

## Design

Commands render to shell scripts, Popup executes them in tmux popups. 
Commands that return values set `returns=True` and handle result parsing.

## Examples

```python
# Confirmation
popup.add(
    GumStyle("Warning", warning=True),
    GumConfirm("Continue?", default=False)
).show()  # Returns: bool

# Selection with tuples
popup.add(
    GumChoose([
        ("save", ":floppy_disk: Save"),
        ("quit", ":x: Quit")
    ])
).show()  # Returns: "save" or "quit"

# Multiple selection
popup.add(
    GumFilter(items, limit=0, fuzzy=True)
).show()  # Returns: List[str]
```