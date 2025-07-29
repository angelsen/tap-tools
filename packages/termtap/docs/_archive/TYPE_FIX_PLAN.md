# Type Fix Plan for termtap

## Issues Found

### 1. resolution.py (3 errors)
All errors stem from functions returning `Optional[str]` or `Optional[SessionWindowPane]` but the code not handling the `None` case.

#### Issue 1: get_pane_id returns Optional[str]
**Lines**: 34, 57
**Problem**: `get_pane_id()` can return `None` but the code assumes it returns `str`
**Fix**: Add None checks and raise appropriate exceptions

#### Issue 2: resolve_service_target returns Optional[SessionWindowPane]
**Line**: 48
**Problem**: `resolve_service_target()` can return `None` but `resolve_target()` expects a non-None Target
**Fix**: Check for None and handle appropriately

### 2. ls.py (1 error)
**Line**: 24
**Problem**: `table_error_response()` returns `list[dict]` but function expects `list[PaneRow]`
**Fix**: Cast the return or adjust the function signature

## Implementation Strategy

### Phase 1: Fix resolution.py
1. Add None checks after `get_pane_id()` calls
2. Raise `PaneNotFoundError` when pane_id is None
3. Handle None from `resolve_service_target()`

### Phase 2: Fix ls.py
1. Import `cast` from typing
2. Cast the error response to match expected type

## Code Changes

### resolution.py fixes:

```python
# Line 33-34 fix:
pane_id = get_pane_id(session, window, pane)
if pane_id is None:
    raise PaneNotFoundError(f"Pane not found: {session}:{window}.{pane}")
return [(pane_id, value)]

# Line 47-48 fix:
resolved_swp = resolve_service_target(value)
if resolved_swp is None:
    raise RuntimeError(f"Service not found: {value}")
return resolve_target(resolved_swp)

# Line 55-57 fix:
pane_id = get_pane_id(session, str(window or 0), str(pane))
if pane_id is None:
    raise PaneNotFoundError(f"Pane not found: {session}:{window or 0}.{pane}")
swp = f"{session}:{window or 0}.{pane}"
return [(pane_id, swp)]
```

### ls.py fix:

```python
from typing import cast

# Line 24:
return cast(list[PaneRow], table_error_response(f"Failed to list panes: {e}"))
```

## Benefits
1. Type safety throughout the codebase
2. Better error messages when panes don't exist
3. Consistent use of domain-specific exceptions
4. No runtime behavior changes for happy path