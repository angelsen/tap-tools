"""Simple symbol registry for consistent ASCII symbols across WebTap."""

# ASCII symbols for consistent UI
SYMBOLS = {
    # Status
    "success": "[OK]",
    "error": "[ERROR]",
    "warning": "[WARN]",
    "info": "[INFO]",
    # States
    "connected": "[x]",
    "disconnected": "[ ]",
    "enabled": "[ON]",
    "disabled": "[OFF]",
    # Navigation
    "current": "->",
    "arrow": "->",
    # Data
    "empty": "-",
    "none": "n/a",
    # Actions
    "paused": "[||]",
    "loading": "...",
}


def sym(name: str) -> str:
    """Get symbol by name, fallback to empty dash."""
    return SYMBOLS.get(name, "-")
