"""ASCII symbol registry for consistent UI display across WebTap commands.

Provides standardized symbols for status indicators, state markers, navigation
elements, and other UI components used throughout the WebTap interface.

PUBLIC API:
  - sym: Get ASCII symbol by name with fallback
"""

# Internal symbol registry
_SYMBOLS = {
    # Status indicators
    "success": "[OK]",
    "error": "[ERROR]",
    "warning": "[WARN]",
    "info": "[INFO]",
    # Connection states
    "connected": "[x]",
    "disconnected": "[ ]",
    "enabled": "[ON]",
    "disabled": "[OFF]",
    # Navigation elements
    "current": "->",
    "arrow": "->",
    # Data placeholders
    "empty": "-",
    "none": "n/a",
    # Action states
    "paused": "[||]",
    "loading": "...",
}


def sym(name: str) -> str:
    """Get ASCII symbol by name with fallback to dash.
    
    Args:
        name: Symbol name from the registry.
        
    Returns:
        ASCII symbol string, or "-" if name not found.
    """
    return _SYMBOLS.get(name, "-")
