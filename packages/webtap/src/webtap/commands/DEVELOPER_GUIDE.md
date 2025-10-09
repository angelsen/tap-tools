# WebTap Commands Developer Guide

This guide documents the patterns and conventions for developing WebTap commands with MCP compatibility.

## Command Patterns (Post-Refinement)

### 1. Simple Commands (No Parameters)
```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def disconnect(state) -> dict:
    """Disconnect from Chrome."""
    # Implementation
```

### 2. Single Required Parameter
```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def navigate(state, url: str) -> dict:
    """Navigate to URL."""
    # Implementation
```

### 3. Optional Boolean/Simple Parameters (Direct)
```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def reload(state, ignore_cache: bool = False) -> dict:
    """Reload current page."""
    # Implementation

# Multiple boolean flags
@app.command(display="markdown", fastmcp={"type": "tool"})
def clear(state, events: bool = True, console: bool = False, cache: bool = False) -> dict:
    """Clear various data stores."""
    # Implementation
```

### 4. Mutually Exclusive Parameters (Direct)
Use direct parameters when you have different ways to identify the same thing:

```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def connect(state, page: int = None, page_id: str = None) -> dict:
    """Connect to Chrome page.
    
    Args:
        page: Connect by page index (0-based)
        page_id: Connect by page ID
        
    Note: Cannot specify both page and page_id.
    """
    if page is not None and page_id is not None:
        return error_response("invalid_parameters", 
            "Cannot specify both 'page' and 'page_id'")
    # Implementation
```

### 5. Multiple Optional Parameters (Direct)
Use direct parameters for cleaner API when parameters are well-defined:

```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def network(state, limit: int = 20, filters: list = None, no_filters: bool = False) -> dict:
    """Show network requests.
    
    Args:
        limit: Maximum results to show
        filters: Specific filter categories to apply
        no_filters: Show everything unfiltered
    """
    # Implementation

# With expression evaluation
@app.command(display="markdown", fastmcp={"type": "tool"})
def body(state, response: int, expr: str = None, decode: bool = True, cache: bool = True) -> dict:
    """Get response body for network request."""
    # Implementation
```

### 6. Mixed Parameters (Direct + Dict)
Use dict only for complex/variable configurations:

```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def resume(state, request: int, wait: float = 0.5, modifications: dict = None) -> dict:
    """Resume a paused request.
    
    Args:
        request: Request row ID
        wait: Wait time for next event
        modifications: Request/response modifications
            - {"url": "..."} - Change URL
            - {"method": "POST"} - Change method
    """
    mods = modifications or {}
    # Implementation
```

### 7. Dynamic Field Discovery (Keep Dict)
Use dict when field names are dynamic/unknown:

```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def events(state, filters: dict = None, limit: int = 20) -> dict:
    """Query CDP events by field values.
    
    Args:
        filters: Field filters (any CDP field name)
            - {"method": "Network.*"}
            - {"status": 200}
            - {"url": "*api*"}
    """
    # Fields are discovered dynamically from CDP events
```

### 8. Action + Config Pattern (Complex Operations)
Keep for commands with varied operations:

```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def filters(state, action: str = "list", config: dict = None) -> dict:
    """Manage filters.
    
    Args:
        action: Operation to perform
            - "list" - Show all filters
            - "add" - Add filter
            - "remove" - Remove filter
        config: Action-specific configuration
            - For add: {"category": "ads", "patterns": ["*ad*"]}
            - For remove: {"patterns": ["*ad*"]}
    """
    cfg = config or {}
    
    if action == "add":
        category = cfg.get("category", "custom")
        patterns = cfg.get("patterns", [])
        # Implementation
```

## MCP Type Requirements

### ❌ Avoid These (Not MCP Compatible)
```python
# Union types
def command(state, param: str | None = None)

# Optional types
from typing import Optional
def command(state, param: Optional[str] = None)

# Complex types
from typing import Dict, List
def command(state, data: Dict[str, List[str]])

# **kwargs
def command(state, **fields)
```

### ✅ Use These Instead
```python
# Simple defaults
def command(state, param: str = "default")
def command(state, param: dict = None)  # pyright: ignore[reportArgumentType]
def command(state, param: list = None)  # pyright: ignore[reportArgumentType]
def command(state, param: bool = False)
def command(state, param: int = 0)
```

## Response Patterns

### Resources (Read-Only Data)
```python
@app.command(display="markdown", fastmcp={"type": "resource", "mime_type": "text/markdown"})
def pages(state) -> dict:
    """List available pages."""
    return table_response(
        title="Chrome Pages",
        headers=["Index", "Title", "URL"],
        rows=rows,
        summary=f"{len(rows)} pages"
    )
```

### Tools (Actions with Side Effects)
```python
@app.command(display="markdown", fastmcp={"type": "tool"})
def navigate(state, url: str) -> dict:
    """Navigate to URL."""
    # Perform action
    return info_response(
        title="Navigation Complete",
        fields={"URL": url, "Status": "Success"}
    )
```

## Error Handling

Always use the error utilities from `_builders.py`:

```python
from webtap.commands._builders import check_connection, error_response

def my_command(state, ...):
    # Check connection first for commands that need it
    if error := check_connection(state):
        return error

    # Validate parameters
    if not valid:
        return error_response("Parameter X must be Y", suggestions=["Try this", "Or that"])

    # Simple errors
    return error_response("Specific error message")
```

## Response Builders

Use builders from `_builders.py`:

```python
from webtap.commands._builders import (
    # Table responses
    table_response,         # Tables with headers, warnings, tips

    # Info displays
    info_response,          # Key-value pairs with optional heading

    # Status responses
    error_response,         # Errors with suggestions
    success_response,       # Success messages with details
    warning_response,       # Warnings with suggestions

    # Code results
    code_result_response,   # Code execution with result display
    code_response,          # Simple code block display

    # Connection helpers
    check_connection,       # Helper for CDP connection validation
    check_fetch_enabled,    # Helper for fetch interception validation
)
```

### Usage Examples

```python
# Table with tips
return table_response(
    title="Network Requests",
    headers=["ID", "URL", "Status"],
    rows=rows,
    summary=f"{len(rows)} requests",
    tips=["Use body(ID) to fetch response body"]
)

# Code execution result
return code_result_response(
    "JavaScript Result",
    code="2 + 2",
    language="javascript",
    result=4
)

# Error with suggestions
return error_response(
    "Not connected to Chrome",
    suggestions=["Run pages()", "Use connect(0)"]
)
```

## Text Over Symbols

Use explicit text instead of symbols for clarity:

```python
# Status text
"Connected" / "Disconnected"
"Enabled" / "Disabled"
"Yes" / "No"

# For empty values
"-" or "None" or ""

# Descriptive status
"3 requests paused" instead of symbols
"Request Failed" instead of error symbols
```

## Decision Tree for Parameter Patterns (Updated)

1. **No parameters?** → Simple command
2. **One required param?** → Single parameter
3. **Few well-defined params?** → Direct parameters with defaults
4. **Multiple ways to identify same thing?** → Direct mutually exclusive params
5. **Dynamic/unknown field names?** → Dict for filters
6. **Complex variable config?** → Dict for modifications
7. **Different operations based on input?** → Action + config pattern

### When to Use Direct Parameters
- Parameters are well-defined and limited (< 5)
- Parameters are commonly used
- Makes the API more intuitive
- Boolean flags or simple types

### When to Keep Dict Parameters
- Field names are dynamic (like CDP event fields)
- Configuration varies significantly by action
- Many optional parameters rarely used together
- Complex nested structures needed

## Examples by Category (Current Implementation)

### Navigation Commands
- `navigate(url: str)` - Single required parameter
- `reload(ignore_cache: bool = False)` - Optional boolean
- `back()`, `forward()` - No parameters

### Query Commands  
- `network(limit: int = 20, filters: list = None, no_filters: bool = False)` - Direct params
- `events(filters: dict = None, limit: int = 20)` - Dict for dynamic fields + limit
- `inspect(event: int = None, expr: str = None)` - Direct optional params
- `body(response: int, expr: str = None, decode: bool = True, cache: bool = True)` - Mixed direct params

### Management Commands
- `connect(page: int = None, page_id: str = None)` - Mutually exclusive direct params
- `clear(events: bool = True, console: bool = False, cache: bool = False)` - Boolean flags
- `filters(action: str = "list", config: dict = None)` - Action + config pattern

### JavaScript & Fetch Commands
- `js(code: str, wait_return: bool = True, await_promise: bool = False)` - Direct params
- `fetch(action: str, options: dict = None)` - Action pattern
- `resume(request: int, wait: float = 0.5, modifications: dict = None)` - Direct + dict

## Testing Your Command

1. **Type checking**: Run `basedpyright` to ensure types are correct
2. **Linting**: Run `ruff check` for code style
3. **REPL mode**: Test with `webtap` command
4. **MCP mode**: Test with `webtap --mcp` command
5. **Markdown rendering**: Verify output displays correctly

## TIPS.md Integration

All commands should be documented in `TIPS.md` for consistent help and MCP descriptions:

```python
from webtap.commands._tips import get_tips, get_mcp_description

# Get MCP description (for fastmcp metadata)
mcp_desc = get_mcp_description("mycommand")

@app.command(
    display="markdown",
    fastmcp={"type": "tool", "description": mcp_desc} if mcp_desc else {"type": "tool"}
)
def mycommand(state, param: str) -> dict:
    """My command description."""
    # ... implementation ...

    # Include tips in response
    tips = get_tips("mycommand", context={"id": some_id})
    return table_response(
        headers=headers,
        rows=rows,
        tips=tips  # Automatically shown as "Next Steps"
    )
```

### Adding to TIPS.md

Add a section for your command:

```markdown
### mycommand
Brief description of what the command does.

#### Examples
\```python
mycommand("param1")              # Basic usage
mycommand("param2", flag=True)   # With options
\```

#### Tips
- **Related command:** `other_command()` - does related thing
- **Advanced usage:** Use with `yet_another()` for X
- **Context aware:** Tips support {id} placeholders from context dict
```

## Checklist for New Commands

- [ ] Use `@app.command()` decorator with `display="markdown"`
- [ ] Add `fastmcp` metadata (type: "resource" or "tool")
- [ ] Use simple types only (no unions, no Optional)
- [ ] Add `# pyright: ignore[reportArgumentType]` for `dict = None`
- [ ] Import builders from `_builders.py`
- [ ] Use `table_response()`, `info_response()`, or `code_result_response()`
- [ ] Check connection with `check_connection()` if needed
- [ ] Add command section to `TIPS.md` with examples and tips
- [ ] Use `get_tips()` to show tips in response
- [ ] Document parameters clearly in docstring
- [ ] Test in both REPL and MCP modes