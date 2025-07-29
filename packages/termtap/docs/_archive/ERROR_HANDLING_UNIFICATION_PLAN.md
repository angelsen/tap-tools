# Error Handling Unification Plan for termtap Modules

## Current State Analysis

After reviewing all module files, here's the current error handling state:

### 1. tmux/*.py Modules

#### resolution.py
- **Good**: Raises descriptive RuntimeErrors with context
- **Pattern**: `raise RuntimeError(f"Service not found: {value}")`
- **Status**: ✅ Follows spec

#### pane.py
- **Good**: Raises specific exceptions (CurrentPaneError) and RuntimeError with context
- **Issues**: Some ValueError raises could be RuntimeError for consistency
- **Status**: ⚠️ Mostly compliant

#### stream.py
- **Good**: Uses try/except for non-critical operations (file I/O)
- **Good**: Returns sensible defaults on failure
- **Issues**: No error raising - all errors are caught silently
- **Status**: ✅ Appropriate for its role

#### session.py, structure.py, core.py
- **Good**: Raises RuntimeError with tmux stderr included
- **Pattern**: `raise RuntimeError(f"Failed to create session: {stderr}")`
- **Status**: ✅ Follows spec

#### exceptions.py
- **Good**: Defines domain-specific exceptions
- **Status**: ✅ Well-structured

### 2. process/*.py Modules

#### detector.py
- **Good**: Returns sensible defaults on failure
- **Good**: Logs errors instead of raising
- **Pattern**: `return ProcessInfo(shell="unknown", process=None, state="unknown")`
- **Status**: ✅ Follows spec for non-critical operations

#### tree.py
- **Good**: Returns empty defaults on OS errors
- **Good**: Logs errors for debugging
- **Status**: ✅ Appropriate error handling

#### handlers/__init__.py
- **Issues**: Raises RuntimeError for missing handler
- **Consider**: Should this return a default handler instead?
- **Status**: ⚠️ May need adjustment

### 3. config.py
- **Good**: Silently handles regex compilation errors
- **Good**: Returns sensible defaults
- **Status**: ✅ Appropriate error handling

## Unification Plan

### Phase 1: Quick Fixes (Low Risk)

1. **pane.py**: Change ValueError to RuntimeError for consistency
   - Line 67: `raise RuntimeError(f"Invalid PID: {stdout}")`
   - Line 206: `raise RuntimeError("Need at least 2 panes for layout")`

2. **handlers/__init__.py**: Consider returning DefaultHandler instead of raising
   ```python
   # Instead of:
   raise RuntimeError(f"No handler for process {process.name}")
   
   # Consider:
   logger.warning(f"No specific handler for {process.name}, using default")
   return DefaultHandler()
   ```

### Phase 2: Consistency Improvements (Medium Risk)

1. **Standardize error messages** across tmux modules:
   - Format: `"Failed to {action}: {details}"`
   - Include stderr/stdout when available
   - Keep messages descriptive but concise

2. **Add missing exception types** to exceptions.py:
   ```python
   class SessionNotFoundError(TmuxError):
       """Raised when a tmux session doesn't exist."""
   
   class PaneNotFoundError(TmuxError):
       """Raised when a tmux pane doesn't exist."""
   ```

3. **Use specific exceptions** where appropriate:
   - Replace generic RuntimeError with domain-specific exceptions
   - Keep RuntimeError for unexpected/system errors

### Phase 3: Documentation and Testing (Low Risk)

1. **Add error handling examples** to module docstrings
2. **Create unit tests** for error cases:
   - Test each error path
   - Verify error messages are helpful
   - Ensure no raw tracebacks leak

## Implementation Priority

1. **High Priority** (Do First):
   - Fix pane.py ValueError → RuntimeError
   - Review handlers/__init__.py behavior

2. **Medium Priority** (Do Next):
   - Standardize error message formats
   - Add specific exception types

3. **Low Priority** (Do Later):
   - Add comprehensive tests
   - Update documentation

## Key Principles to Maintain

1. **Modules raise, commands catch**: Modules should raise descriptive errors, commands transform them
2. **Be specific**: Use descriptive error messages that help users understand what went wrong
3. **Include context**: Always include relevant IDs, names, or values in error messages
4. **Log for debugging**: Use logger.debug() for recoverable issues, logger.error() for unexpected failures
5. **Return defaults for non-critical**: Process detection and similar operations should degrade gracefully

## Risk Assessment

- **Low Risk**: Changing ValueError to RuntimeError, standardizing messages
- **Medium Risk**: Changing handler behavior (needs testing)
- **High Risk**: None identified

## Next Steps

1. Review this plan with maintainer
2. Implement Phase 1 fixes
3. Test changes in REPL
4. Proceed with Phase 2 if Phase 1 successful
5. Document any new patterns discovered