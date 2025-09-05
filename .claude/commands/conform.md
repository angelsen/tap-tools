---
description: Conform a module to project conventions with formatting and testing
argument-hint: <module-path>
---

Conform module to conventions: $ARGUMENTS

Use debug-bridge terminal session "epic-swan" to execute commands.

Follow this workflow:

1. **Format** the module first:
   - `make format TARGET=$ARGUMENTS`
   - This applies ruff formatting to Python files and shfmt to shell scripts

2. **Stage changes** after formatting:
   - Suggest user stages changes with `git add $ARGUMENTS`
   - This creates a checkpoint before semantic changes

3. **Conform to conventions** (with context awareness):
   - `make conform-module TARGET=$ARGUMENTS`
   - This applies naming conventions and docstring templates
   - **Important**: Check for double-privatization patterns:
     - Files in `services/`, `utils/` directories shouldn't have underscore class names
     - Functions in `_*.py` files shouldn't have underscore prefixes
   - Consider directory structure as organizational context

4. **Verify** the changes:
   - `ruff check $ARGUMENTS` to ensure no linting errors
   - Test that termtap still runs properly by:
     * `uv run python -m termtap` to start the REPL
     * `bash("echo 'test'")` to test command execution
     * `exit()` to close the REPL

5. **Prepare for commit**:
   - Summarize what changed (formatting vs semantic changes)
   - Suggest appropriate commit message

Remember:
- Always test after conforming to conventions
- Keep commits focused (one module at a time)
- Use descriptive commit messages