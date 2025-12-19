"""WebTap command modules for browser automation.

Commands are imported directly by app.py to register with the ReplKit2 app.
In CLI mode, only CLI-compatible commands are imported to avoid Typer issues.

Module Organization:
  - _builders.py: Response builders using ReplKit2 markdown elements
  - _tips.py: Parser for TIPS.md documentation
  - _utils.py: Shared utilities for command modules
  - _code_generation.py: Code generation utilities for HTTP bodies
  - connection.py: Chrome browser connection management
  - navigation.py: Browser navigation commands
  - network.py: Network request monitoring
  - console.py: Console message display
  - filters.py: Filter management
  - fetch.py: Request interception
  - javascript.py: JavaScript execution
  - request.py: Request data extraction with Python expressions
  - to_model.py: Generate Pydantic models from responses
  - quicktype.py: Generate type definitions via quicktype
  - selections.py: DOM element selection and inspection
  - setup.py: Component installation
  - launch.py: Browser launch helpers

Note: Files prefixed with underscore are internal utilities not exposed as commands.
"""

# No imports needed here - app.py imports commands directly
