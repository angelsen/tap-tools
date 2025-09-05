---
description: Systematically enforce Python and shell conventions across the codebase
argument-hint: [target-path]
allowed-tools: Read, Edit, MultiEdit, Grep, Glob, Task
---

Apply comprehensive code conventions to ${ARGUMENTS:-packages/termtap/src/termtap} using intelligent orchestration.

**Your task: Orchestrate convention enforcement thoughtfully, avoiding mechanical over-application.**

## Guiding Principles

**Avoid Double-Privatization**: 
- If a directory implies internal (`services/`, `internal/`, `utils/`) → classes/functions inside don't need underscores
- If a file starts with `_` → functions inside don't need underscores
- Apply privacy indicators at ONE level only - the most meaningful one

**Context-Aware Documentation**:
- PUBLIC API sections only where actually public (in `__init__.py`, main app files)
- Internal modules get simple purpose docstrings
- Don't over-document obvious internal utilities
- Match documentation depth to the code's importance

**Thoughtful Application**:
- Consider existing patterns in the codebase
- Respect directory structure as organizational context
- Use underscores to clarify, not to blindly mark everything internal
- Prefer clarity over rigid rule-following

## Phase 1: Dependency Analysis & PUBLIC API Setup

**Map the dependency hierarchy:**
- Scan all modules to understand imports and dependencies
- Identify trunk modules (main interfaces, apps, entry points)
- Identify leaf modules (utilities with no internal dependencies)
- Build the dependency tree from trunk to leaf

**For each module (trunk-to-leaf order):**
- Analyze what functions/classes are imported by higher-level modules
- Those imported items → PUBLIC API (no underscore)
- Everything else → Consider context before adding underscores
- Update the `__init__.py` with proper PUBLIC API docstring ONLY if it's a public module:

```python
"""Brief description of this module.

PUBLIC API:
  - function_name: Brief description
  - ClassName: Brief description
"""

from .submodule import function_name, ClassName
# Only import PUBLIC API items

__all__ = ["function_name", "ClassName"]
```

For internal modules, keep it simple:
```python
"""Brief description of this internal module."""
# No PUBLIC API section needed
```

## Phase 2: Convention Application

Apply conventions in dependency-safe order using specialized agents:

**Leaf files first** (standalone utilities):
- Use python-file-enforcer agent for individual .py files
- Agent will check context (file name, directory) before applying underscores
- Documentation level should match file importance

**Core modules** (dependency order):
- Use python-module-enforcer agent for modules with __init__.py
- Agent will respect directory structure (e.g., `services/` implies internal)
- Avoid mechanical underscore prefixes where context is clear

**Shell scripts** (if found):
- Use shell-script-enforcer agent for safety and modern practices

## Phase 3: Verification & Summary

- Run basic checks to ensure no import breakage
- Verify no double-privatization patterns were introduced
- Provide comprehensive summary of changes made
- Report any decisions that required judgment calls

## Orchestration Requirements

**For maximum efficiency:** Invoke tools in parallel when operations are independent. 

**Be thoughtful:** Apply conventions based on context, not mechanical rules. When in doubt, prefer simpler, cleaner names.

**Handle complexity:** Different parts of the codebase may have different patterns - respect them.

**Progress reporting:** Provide clear updates as you work through each phase, including reasoning for non-obvious decisions.

## Examples of Good Judgment

**Good**: `services/network.py` contains `class NetworkService` (no underscore - directory provides context)
**Bad**: `services/network.py` contains `class _NetworkService` (double-privatization)

**Good**: `_utils.py` contains `def format_output()` (no underscore - file already private)
**Bad**: `_utils.py` contains `def _format_output()` (double-privatization)

**Good**: `api.py` has simple docstring for internal FastAPI routes
**Bad**: `api.py` has PUBLIC API section for routes that aren't exported

Start immediately with Phase 1 dependency analysis, keeping these principles in mind throughout.