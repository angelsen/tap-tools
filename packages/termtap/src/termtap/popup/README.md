# Tmux Popup System

Native tmux popup windows with gum for rich terminal UIs.

## Features

- **Tmux-native**: Uses `tmux display-popup` for proper windowing
- **Gum-powered**: Rich interactive components (choose, input, table, pager)
- **Value/display separation**: Clean programmatic interfaces
- **Theme support**: Consistent styling across popups
- **Auto-sizing**: Smart defaults, optional dimensions
- **Temp file IPC**: Reliable result passing

## Quick Start

```python
from termtap.popup import Popup, quick_confirm

# Simple confirmation
if quick_confirm("Proceed with operation?"):
    print("Confirmed")

# Choice with values
p = Popup(title="Action")
choice = p.choose([
    ("save", "Save Changes"),
    ("discard", "Discard"),
    ("cancel", "Cancel")
])
print(f"Selected: {choice}")  # Returns 'save', not 'Save Changes'

# Table selection
rows = [["1", "nginx", "active"], ["2", "redis", "stopped"]]
p.table(rows, headers=["PID", "Name", "Status"], return_column=2)
```

## Components

### Core Classes
- `Popup`: Main builder for tmux popups
- `Theme`: Style configuration dataclass

### Methods
- `choose()`: Single/multi selection with optional value/display pairs
- `table()`: Tabular selection with column return
- `input()`: Text input with validation
- `confirm()`: Yes/no confirmation
- `pager()`: Scrollable content viewer

### Display Methods
- `header()`, `info()`, `success()`, `warning()`, `error()`
- `text()`, `separator()`

### Quick Functions
- `quick_confirm()`, `quick_choice()`, `quick_input()`, `quick_info()`

## Examples

See `examples.py` for complete examples:
```python
from termtap.popup.examples import *
basic_popup()
choice_with_values()
table_selection()
ssh_workflow()
```

## Architecture

1. **Build Phase**: Accumulate gum commands in script
2. **Display Phase**: Execute script in tmux popup
3. **Result Phase**: Read results from temp files
4. **Cleanup**: Auto-remove temp files

## Notes

- Requires tmux and gum installed
- Auto-sizes by default (no width/height specified)
- Interactive components block until user responds
- All temp files cleaned up automatically