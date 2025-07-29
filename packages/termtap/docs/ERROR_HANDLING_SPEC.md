# Error Handling Specification for termtap

## Core Principles

1. **User-friendly errors**: Show clear, actionable error messages
2. **No implementation details**: Hide internal tracebacks and implementation details
3. **Consistent patterns**: All commands handle errors the same way
4. **Clean output**: Single, focused error message in the REPL

## Scope

This spec covers Python exception handling in termtap commands. It does NOT cover:
- Errors that occur inside tmux shells (those are just command output)
- System-level tmux errors (handled by showing tmux's error message)
- Process failures inside panes (shown as normal output)

## Error Categories

### 1. Target Resolution Errors

#### Ambiguous Target (Multiple Panes)
- **When**: Target resolves to multiple panes for single-pane commands
- **Exception**: `RuntimeError` from `resolve_or_create_target()`
- **User Message**:
  ```
  Target 'demo' has 2 panes. Please specify:
    - demo:0.0
    - demo:0.1
    - demo.backend    # if services exist
    - demo.frontend
  ```

#### Target Not Found
- **When**: Target doesn't exist and cannot be created
- **Exception**: `RuntimeError` from resolution functions
- **User Message**:
  ```
  Target not found: nonexistent
  ```

#### Service Not Found
- **When**: Service target doesn't exist
- **Exception**: `RuntimeError` with "Service not found"
- **User Message**:
  ```
  Service not found: demo.backend
  Use 'init_list()' to see available init groups.
  ```

### 2. Operational Errors

#### Current Pane Error
- **When**: Attempting forbidden operation on current pane
- **Exception**: `CurrentPaneError` from `send_keys()`
- **User Message**:
  ```
  Cannot send commands to current pane (%42)
  ```

#### Tmux Command Failed
- **When**: Tmux command returns non-zero exit code
- **Exception**: `RuntimeError` from tmux operations
- **User Message**: Pass through tmux's stderr

## Implementation Patterns

### Pattern 1: Commands with Single Pane Target (bash, interrupt)

```python
def command(state, target: Target = "default", ...):
    try:
        pane_id, swp = resolve_or_create_target(target)
    except RuntimeError as e:
        error_str = str(e)
        
        # Handle ambiguous target with service suggestions
        if "matches" in error_str and "panes" in error_str:
            try:
                panes = resolve_target(target)
                targets = [swp for _, swp in panes]
                
                # Add service targets if available
                session = panes[0][1].split(":")[0]
                cm = get_config_manager()
                if session in cm._init_groups:
                    group = cm._init_groups[session]
                    targets.extend([s.full_name for s in group.services])
                
                message = (
                    f"Target '{target}' has {len(panes)} panes. Please specify:\n" +
                    "\n".join(f"  - {t}" for t in targets)
                )
                return markdown_error_response(message)
            except:
                # Fallback to original error
                return markdown_error_response(f"Target error: {error_str}")
        
        # Handle service not found
        elif "Service" in error_str and "not found" in error_str:
            message = (
                f"Service not found: {target}\n"
                f"Use 'init_list()' to see available init groups."
            )
            return markdown_error_response(message)
        
        # Generic target error
        else:
            return markdown_error_response(f"Target error: {error_str}")
```

### Pattern 2: Commands with Multi-Pane Support (read, ls)

```python
def command(state, target: Target = "default", ...):
    try:
        panes = resolve_target(target)
    except RuntimeError as e:
        error_str = str(e)
        
        # Handle service not found
        if "Service" in error_str and "not found" in error_str:
            message = (
                f"Service not found: {target}\n"
                f"Use 'init_list()' to see available init groups."
            )
            return markdown_error_response(message)
        
        # Handle target not found
        elif "not found" in error_str or "No panes found" in error_str:
            return markdown_error_response(f"Target not found: {target}")
        
        # Generic target error
        else:
            return markdown_error_response(f"Target error: {error_str}")
    
    if not panes:
        return markdown_error_response(f"No panes found for target: {target}")
    
    # Handle single vs multiple panes
    if len(panes) == 1:
        # Single pane logic
    else:
        # Multi-pane logic
```

### Pattern 3: Error Response Format

For markdown display commands:
```python
def markdown_error_response(message: str) -> dict:
    return {
        "elements": [{"type": "text", "content": f"Error: {message}"}],
        "frontmatter": {"status": "error"}
    }
```

For table display commands:
```python
def table_error_response(message: str) -> list:
    # Log the error and return empty list
    logger.warning(f"Command failed: {message}")
    return []
```

For string display commands:
```python
def string_error_response(message: str) -> str:
    return f"Error: {message}"
```

## Error Message Helpers

Note: In the current implementation, each command handles its own error formatting
inline rather than using shared helpers. This keeps the error handling module 
simple and avoids circular import issues.

The `errors.py` module provides only the generic response formatters:
- `markdown_error_response(message: str)`
- `table_error_response(message: str)`
- `string_error_response(message: str)`

Commands handle their own business logic for enhanced error messages (like adding
service suggestions to ambiguous target errors).

## Module-Level Exception Handling

### Resolution Module (`tmux/resolution.py`)
- **DO**: Raise `RuntimeError` with descriptive messages
- **DON'T**: Try to format user-friendly messages here
- **Example**:
  ```python
  raise RuntimeError(f"Target '{target}' matches {len(panes)} panes - too ambiguous for creation")
  ```

### Tmux Operations (`tmux/*.py`)
- **DO**: Let tmux errors bubble up with stderr included
- **DON'T**: Catch and re-wrap tmux errors unnecessarily
- **Example**:
  ```python
  if code != 0:
      raise RuntimeError(f"Failed to create session: {stderr}")
  ```

### Process Detection (`process/detector.py`)
- **DO**: Return sensible defaults on failure
- **DON'T**: Raise exceptions for non-critical failures
- **Example**:
  ```python
  try:
      # detection logic
  except Exception as e:
      logger.warning(f"Process detection failed: {e}")
      return ProcessInfo(shell="unknown", process=None, state="unknown")
  ```

## Command-Level Exception Handling

### Commands MUST:
1. Catch exceptions at the command boundary
2. Transform exceptions into user-friendly messages
3. Return proper response format (never let exceptions escape)
4. Use `from None` to suppress tracebacks when providing better errors

### Commands MUST NOT:
1. Show raw tracebacks to users
2. Let exceptions propagate to ReplKit2
3. Catch exceptions deep in logic (let them bubble to command level)

## Response Formats by Display Type

### Markdown Display Commands (bash, read, init)
```python
# Success
return {
    "elements": [...],
    "frontmatter": {...}
}

# Error
return {
    "elements": [{"type": "text", "content": f"Error: {message}"}],
    "frontmatter": {"status": "error"}
}
```

### Table Display Commands (ls, init_list)
```python
# Success
return [{"col1": "val1", ...}, ...]

# Error - log and return empty
logger.warning(f"Command failed: {message}")
return []
```

### String Display Commands (kill)
```python
# Success
return "Success message"

# Error
return f"Error: {message}"
```

## Exception Suppression

- Use `from None` to suppress exception chaining when providing custom errors
- This prevents double tracebacks in the REPL
- Example:
  ```python
  except RuntimeError as e:
      if "matches" in str(e):
          raise ValueError("Better error message") from None
      else:
          raise  # Re-raise unexpected errors
  ```

## Logging Strategy

1. **Commands**: Log warnings for handled errors
2. **Modules**: Log debug for recoverable issues
3. **Never**: Use print() for error messages

## Testing Requirements

Each command should have tests for:
1. Ambiguous targets (sessions/windows with multiple panes)
2. Non-existent targets
3. Invalid service names
4. Current pane operations (where applicable)
5. Tmux command failures

## Implementation Checklist

For each command:
- [ ] All exceptions caught at command boundary
- [ ] User-friendly error messages
- [ ] Proper response format for errors
- [ ] No raw tracebacks shown
- [ ] `from None` used for custom errors
- [ ] Error cases tested

## Implementation Status

✅ **Completed Implementation**

1. ✅ Created minimal `termtap.errors` module with generic response formatters
2. ✅ Updated all commands to handle errors locally:
   - `bash.py` - Handles ambiguous targets with service suggestions
   - `interrupt.py` - Same error handling pattern as bash
   - `init.py` - Comprehensive error handling for all operations
   - `read.py` - Handles service and target not found errors
   - `ls.py` - Graceful degradation for process detection failures
   - `kill()` in init.py - Simple error responses
3. ✅ Fixed double error display issue (frontmatter shows only `{"status": "error"}`)
4. ✅ No raw tracebacks shown to users

## Key Design Decision

We chose **Option 1: Keep Service Logic in Commands** to avoid circular imports and maintain a clean architecture. The error handling module (`errors.py`) remains generic and simple, while each command handles its own business logic for enhanced error messages.