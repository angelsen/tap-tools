---
description: Analyze project modules to identify their purpose and public APIs
argument-hint: <project-path>
---

Analyze the modules in $ARGUMENTS to identify their purpose and determine public APIs.

For each Python module in the project:

1. **Examine the module structure**:
   - List all .py files in the module
   - Read current __init__.py to see existing exports
   - Identify the module's overall purpose

2. **Analyze function/class usage**:
   - Search for imports of this module from other parts of the codebase
   - Identify which functions/classes are used externally vs internally
   - Look for patterns that indicate public vs private intent

3. **Determine the PUBLIC API**:
   - Functions/classes used by other modules → PUBLIC (no underscore)
   - Helper functions only used within module → PRIVATE (underscore prefix)
   - Data classes that are part of return types → PUBLIC
   - Internal state/implementation details → PRIVATE

4. **Document findings**:
   - Summarize each module's purpose
   - List identified PUBLIC API items
   - Explain reasoning for public/private decisions
   - Note any unclear cases that need human judgment

Output format:
```
Module: <module_name>
Purpose: <brief description>
PUBLIC API:
  - function_name: <what it does>
  - ClassName: <what it represents>
Internal functions that should be private:
  - _helper_function
  - _InternalClass
```