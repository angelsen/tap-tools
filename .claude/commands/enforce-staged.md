---
description: Apply Python conventions starting from staged files and ripple outward
argument-hint: (no arguments needed)
allowed-tools: Bash, Read, Edit, MultiEdit, Grep, Glob, Task
---

Apply Python naming conventions starting from staged files, then fix all necessary imports.

**Your task: Use staged files as the epicenter of convention enforcement, rippling changes outward as needed.**

## Guiding Principles

**Avoid Double-Privatization**:
- If a file starts with `_` → functions inside don't need underscores
- If in a directory like `services/`, `internal/`, `utils/` → consider keeping clean names
- Apply privacy indicators at ONE meaningful level only

**Context-Aware Application**:
- Check directory structure before applying underscores
- Respect existing organizational patterns
- Use underscores to clarify, not mechanically mark everything

## Phase 1: Map the Territory

1. Get staged Python files: `git diff --cached --name-only --diff-filter=ACMR | grep '\.py$'`
2. For each staged file, determine:
   - Is it a trunk (app/main entry point)?
   - Is it a leaf (no internal dependencies)?
   - Is it mid-tree (both imports and is imported)?
   - What's its module structure and directory context?

## Phase 2: Determine PUBLIC APIs

**For staged __init__.py files:**
- These define the module's PUBLIC API explicitly
- Everything in `__all__` or imported = PUBLIC
- Everything else → Consider context before adding underscores

**For staged module members:**
- Check if their module's __init__.py imports them → PUBLIC
- Check if external modules import them → PUBLIC
- If in `services/`, `utils/` directory → Often keep clean names
- Otherwise → PRIVATE only if it clarifies organization

**For staged standalone files:**
- Check what imports them across the codebase → those stay PUBLIC
- If file starts with `_` → Keep functions clean (no double-privatization)
- Everything else → Consider context

## Phase 3: Apply Conventions & Ripple

**Launch specialized agents for staged files:**
1. For each staged file, determine the appropriate agent:
   - Any Python file that's part of a module (has __init__.py in its directory or parent directories) → Launch `python-module-enforcer` agent for the entire module
   - Standalone Python file (NOT in a module, no __init__.py anywhere in its path) → Launch `python-file-enforcer` agent
   - Shell script → Launch `shell-script-enforcer` agent
2. Provide agents with:
   - Target path of the staged file or its parent module
   - Context about its position in dependency tree (trunk/leaf/mid-tree)
   - **Directory context** (is it in `services/`, `utils/`, etc.)
   - Note to avoid double-privatization
3. Launch agents in parallel when possible for efficiency
4. Let agents handle:
   - Context-aware convention application (not mechanical)
   - Import updates across the codebase
   - Ripple effects to dependent files

**Verify agent results:**
1. Check for any double-privatization patterns
2. Ensure no unnecessary underscores were added
3. Verify all imports were properly updated
4. Fix any edge cases the agents might have missed

## Phase 4: Verification

1. Run `basedpyright` on affected files (staged + modified)
2. Run `ruff check --fix` on affected files
3. Show summary of:
   - Staged files with conventions applied
   - Unstaged files that needed import fixes
   - Any context-aware decisions made
   - Any remaining issues

## Key Strategy

- **Staged files are the catalyst**: They drive the convention changes
- **Context matters**: Directory structure provides organizational context
- **Avoid mechanical application**: Think before adding underscores
- **Use specialized agents wisely**: They now understand context
- **Module boundaries matter**: Respect __init__.py as the API contract
- **Parallel execution**: Launch multiple agents concurrently when possible

Start by identifying staged Python files and mapping their position in the dependency tree, considering both module structure and directory context.