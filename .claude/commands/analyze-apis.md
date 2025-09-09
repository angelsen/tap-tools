---
description: Analyze project modules to identify their purpose and public APIs
argument-hint: [project-path]
---

Analyze the modules in ${ARGUMENTS:-packages/termtap/src/termtap} to identify their purpose and determine public APIs.

Use a **trunk-to-leaf analysis approach** (demand-driven API discovery):

1. **Identify the dependency hierarchy**:
   - Map which modules import from other internal modules
   - Find trunk modules (main interfaces, apps, high-level orchestrators)
   - Find leaf modules (pure utilities, no internal dependencies)
   - Build the import dependency tree

2. **Start with trunk modules** (main application entry points):
   - These define the external contract - what users/clients actually call
   - Their imports reveal what they demand from dependencies
   - Clear separation between user-facing API and internal orchestration

3. **Work down the dependency chain** (demand-driven):
   - For each dependency level, what functions/classes are imported by higher levels?
   - Those imported items → PUBLIC API (no underscore)
   - Everything else → Consider context before marking PRIVATE
   - Each level's PUBLIC API is determined by what levels above it actually use

4. **Apply context-aware documentation**:
   - **Main entry points** (`__init__.py` of exported packages):
     ```python
     """Brief description of this module.

     PUBLIC API:
       - function_name: Brief description
       - ClassName: Brief description
     """
     ```

   - **Internal modules** (in subdirectories like `services/`, `utils/`, `internal/`):
     ```python
     """Brief description of this internal module."""
     # No PUBLIC API section needed - it's internal
     ```

   - **Helper modules** (files starting with `_`):
     ```python
     """Brief description of this utility module."""
     # Simple docstring sufficient
     ```

5. **Consider directory context**:
   - Modules in `services/`, `utils/`, `internal/` → Often don't need PUBLIC API docs
   - Only document PUBLIC API where it's genuinely public (exported to users)
   - Avoid over-documentation of obvious internal utilities

**Principles to follow**:
- Don't force PUBLIC API documentation everywhere
- Respect directory structure as organizational context
- Simple, clear docstrings for internal modules
- Comprehensive PUBLIC API only for true entry points

**Goal**: After this command, modules should have appropriate documentation that matches their actual purpose and visibility, not mechanical PUBLIC API sections everywhere.
