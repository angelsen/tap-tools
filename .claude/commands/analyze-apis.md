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
   - Everything else → PRIVATE implementation (underscore prefix)
   - Each level's PUBLIC API is determined by what levels above it actually use

4. **Refine iteratively** (2 steps forward, 1 step back):
   - If lower-level analysis reveals a trunk module should expose more/less, refine
   - If a leaf module needs to support trunk requirements, adjust accordingly
   - Converge on a consistent API hierarchy

5. **Update all __init__.py docstrings** (trunk to leaf order):
   - For each module, analyze what should be PUBLIC API based on external imports
   - Edit the __init__.py file to add/update the docstring with PUBLIC API list
   - Use this exact format:

```python
"""Brief description of this module.

PUBLIC API:
  - function_name: Brief description
  - ClassName: Brief description
"""
```

   - If __init__.py doesn't exist, create it with the docstring and appropriate imports
   - Document your reasoning for each PUBLIC API decision
   - Note any unclear cases that need human judgment

**Goal**: After this command, all __init__.py files should have proper PUBLIC API docstrings that the convention agents can read and use.