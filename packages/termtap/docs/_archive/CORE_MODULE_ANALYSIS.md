# Core Module Analysis: Session vs Pane Migration Issues

## 1. Inconsistent Session vs Pane Usage

### execute.py Issues:

1. **`get_handler_for_session()` still uses session naming**:
   - Line 95: `get_handler_for_session(pane_id, send_info.process)`
   - Line 134: `get_handler_for_session(pane_id, wait_info.process)`
   - Function name still refers to "session" but takes pane_id parameter
   - This is confusing and should be renamed to `get_handler_for_pane()`

2. **Config resolution issues**:
   - Line 78: `config = get_pane_config(f"{session}:0.0")`
   - This assumes new sessions always start at window 0, pane 0
   - The function `get_pane_config()` is called but `get_target_config()` is imported
   - Import mismatch: imports `get_target_config` but uses `get_pane_config`

3. **Stream manager call signature mismatch**:
   - Line 85: `stream = state.stream_manager.get_stream(pane_id, session_window_pane)`
   - The StreamManager.get_stream() now requires two parameters but this wasn't consistently updated

### control.py Issues:

1. **Incorrect send_keys parameter**:
   - Line 27: `send_keys(pane_id, "C-c")`
   - Should be `"\x03"` (as it was before) not `"C-c"`
   - The comment says "Ctrl+C" but the code was changed incorrectly

2. **Function naming inconsistency**:
   - `_send_interrupt()` is internal but documented as taking a pane
   - Other control functions like `_send_sigterm()` were not shown in diff but may need updates

## 2. Missing Pane-First Conversions

### Import Issues:

1. **__init__.py**:
   - Line 12: `from ..types import CommandResult`
   - CommandResult is now imported from types module, but the import structure is fragmented

2. **Missing error handling for pane resolution**:
   - execute.py doesn't handle all cases where `resolve_target_to_pane()` might fail
   - Only catches RuntimeError for non-existent targets

## 3. Potential Bugs from Migration

### Major Issues:

1. **Circular dependency risk**:
   - execute.py imports from types
   - types module might import from other modules
   - Need to verify no circular imports were introduced

2. **State synchronization**:
   - ProcessInfo now includes `pane_id` field
   - All ProcessInfo creations were updated, but return values need verification

3. **Config Manager not properly initialized**:
   - Line 59: `config_manager = get_config_manager()`
   - Config manager is a singleton but error handling is missing

4. **Stream lifecycle management**:
   - Stream start/stop lifecycle is unclear
   - Line 88: `stream.start()` returns bool but error not properly handled
   - No cleanup on error conditions

## 4. Control Flow Issues

### Command Execution Flow:

1. **Target resolution happens twice**:
   - First attempt at line 63
   - Second attempt at line 82 after session creation
   - This could be optimized

2. **Mark naming inconsistency**:
   - Line 91: `stream.mark_command(cmd_id, command)`
   - Line 123: `stream.mark_read("last_read")`
   - Different marking strategies without clear documentation

3. **Error propagation**:
   - CommandResult with empty pane_id/session_window_pane on error (lines 68-74)
   - Should these be None instead of empty strings?

## Recommendations

1. **Rename functions for consistency**:
   ```python
   # In detector.py
   get_handler_for_pane()  # not get_handler_for_session()
   ```

2. **Fix import mismatches**:
   ```python
   # In execute.py
   from ..config import get_config_manager  # not get_target_config
   ```

3. **Fix control character**:
   ```python
   # In control.py
   send_keys(pane_id, "\x03")  # not "C-c"
   ```

4. **Add proper error handling**:
   ```python
   # In execute.py
   if not stream.start():
       logger.error(f"Failed to start streaming for pane {pane_id}")
       # Consider returning error result here
   ```

5. **Document the pane resolution strategy**:
   - When to use pane_id vs session_window_pane
   - How to handle non-existent targets
   - Stream lifecycle management

6. **Consider adding type guards**:
   ```python
   # Ensure pane_id is valid format
   if not pane_id.startswith('%'):
       raise ValueError(f"Invalid pane_id format: {pane_id}")
   ```

## Summary

The core module has been partially migrated to pane-first architecture, but several inconsistencies remain:
- Function naming still references "sessions" 
- Import statements don't match actual function calls
- Error handling for pane resolution is incomplete
- Control flow could be optimized to avoid duplicate resolution
- Stream lifecycle management needs clarification

These issues should be addressed to complete the pane-first migration and ensure robust operation.