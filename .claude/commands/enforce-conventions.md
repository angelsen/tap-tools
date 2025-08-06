---
description: Systematically enforce Python and shell conventions across the codebase
argument-hint: [target-path]
allowed-tools: Read, Edit, MultiEdit, Grep, Glob, Task
---

Apply comprehensive code conventions to ${ARGUMENTS:-packages/termtap/src/termtap} using intelligent orchestration.

**Your task: Orchestrate the complete convention enforcement pipeline systematically and efficiently.**

## Phase 1: Dependency Analysis & PUBLIC API Setup

**Map the dependency hierarchy:**
- Scan all modules to understand imports and dependencies
- Identify trunk modules (main interfaces, apps, entry points)
- Identify leaf modules (utilities with no internal dependencies)
- Build the dependency tree from trunk to leaf

**For each module (trunk-to-leaf order):**
- Analyze what functions/classes are imported by higher-level modules
- Those imported items → PUBLIC API (no underscore)
- Everything else → PRIVATE (gets underscore prefix)
- Update the `__init__.py` with proper PUBLIC API docstring:

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

## Phase 2: Convention Application

Apply conventions in dependency-safe order using specialized agents:

**Leaf files first** (standalone utilities):
- Use python-file-enforcer agent for individual .py files
- Apply naming conventions and enhance documentation

**Core modules** (dependency order):
- Use python-module-enforcer agent for modules with __init__.py
- Agents can now read the PUBLIC API lists you created
- Apply underscore prefixes to non-PUBLIC functions automatically

**Shell scripts** (if found):
- Use shell-script-enforcer agent for safety and modern practices

## Phase 3: Verification & Summary

- Run basic checks to ensure no import breakage
- Provide comprehensive summary of all changes made
- Report any issues that need manual attention

## Orchestration Requirements

**For maximum efficiency:** Invoke tools in parallel when operations are independent. 

**Be comprehensive:** Process the entire target systematically, handling both individual files and complex module hierarchies.

**Handle errors gracefully:** If a module fails, continue with others and report issues clearly.

**Progress reporting:** Provide clear updates as you work through each phase.

Start immediately with Phase 1 dependency analysis and PUBLIC API setup.