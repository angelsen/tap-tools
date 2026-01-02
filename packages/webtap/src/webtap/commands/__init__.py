"""WebTap command modules for browser automation.

Commands are imported directly by app.py to register with the ReplKit2 app.
In CLI mode, only CLI-compatible commands are imported to avoid Typer issues.

Module Organization:
  Internal utilities (prefixed with underscore):
    _builders.py    - Response builders using ReplKit2 markdown elements
    _tips.py        - Parser for TIPS.md documentation
    _utils.py       - Shared utilities for command modules
    _code_generation.py - Code generation utilities for HTTP bodies

  Command modules (each registers commands via @app.command decorator):
    connection.py   - Chrome browser connection management
    console.py      - Console message display
    fetch.py        - Request interception
    filters.py      - Filter management
    javascript.py   - JavaScript execution
    launch.py       - Browser launch helpers
    navigation.py   - Browser navigation commands
    network.py      - Network request monitoring
    quicktype.py    - Generate type definitions via quicktype
    request.py      - Request data extraction with Python expressions
    selections.py   - DOM element selection and inspection
    setup.py        - Component installation
    to_model.py     - Generate Pydantic models from responses
"""
