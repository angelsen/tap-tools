---
description: Create handoff summary and onboard next colleague
argument-hint: <summary-path> [pre-handoff-instructions]
allowed-tools: Write, Read, Glob, mcp__termtap__send
---

Write handoff summary to: $1

## Pre-Handoff Instructions

$2

## Tasks

1. **Create Summary File** at `$1`

   Required sections:
   - Accomplishments (what was done this session)
   - Current Status (production ready / in development / blocked)
   - Key Files (architecture docs, changes, test evidence)
   - Next Steps (check `.claude/specs/*/tasks.md` for active specs)
   - Future Work (refactoring opportunities, enhancements)

2. **Send Onboarding Message to Colleague**

   Use `mcp__termtap__send` WITHOUT target parameter (sends message to colleague).

   Include:
   - Session summary
   - Path to summary file
   - Next steps
   - CRITICAL: Local resources reminder

## CRITICAL Reminder for Colleague

**BEFORE writing any new code**, use task agents to identify relevant examples:

### Example Workflow
```
Task: Add new WebTap command

FIRST - Search for patterns:
  "Use task agent to search for:
  1. Command registration patterns
  2. Error handling examples
  3. Display formatting patterns

  In: packages/webtap/src/webtap/commands/*.py"

THEN - Write code based on found examples
```

### Available Project Resources
- **WebTap commands:** packages/webtap/src/webtap/commands/
- **Services:** packages/webtap/src/webtap/services/
- **Vision doc:** packages/webtap/src/webtap/VISION.md
- **Developer guide:** packages/webtap/src/webtap/commands/DEVELOPER_GUIDE.md
- **Tips:** packages/webtap/src/webtap/commands/TIPS.md

### Why This Matters
- ✓ Find concrete implementation examples
- ✓ Match existing patterns and conventions
- ✓ Understand architecture decisions
- ✓ Faster than guessing

**Search the codebase first - don't reinvent patterns!**

## Message Structure

Include in your onboarding message:

1. **What was accomplished today**
   - Key features implemented
   - Bugs fixed
   - Architecture decisions

2. **Current system status**
   - Production ready? In development?
   - Known issues or blockers

3. **Important files**
   - Latest summary location
   - Architecture docs (e.g., PIPELINE_ARCHITECTURE.md)
   - Test evidence (extension.log.jsonl)

4. **Next steps**
   - Immediate tasks (if any)
   - Future refactoring opportunities
   - Nice-to-have improvements

5. **Local resources reminder**
   - Copy the "CRITICAL Reminder" section above

## Example Message Template

```
Hey Colleague! 👋

[Summary of today's work]

📄 Key Documents:
- Latest handoff: path/to/SUMMARY_*.md
- Architecture: path/to/ARCHITECTURE.md

✅ Status: [Production ready / In development / Needs testing]

🎯 Next Steps:
[Immediate tasks or "No immediate tasks - system is stable"]

🔮 Future Enhancements:
[Refactoring opportunities, optimizations]

⚠️ CRITICAL - Before Coding:
Use task agents to search local resources for examples:
[Include resources list and workflow example]

Good luck! 🚀
```

## Execution

1. Create the summary file at the specified path
2. Send the onboarding message using: `mcp__termtap__send` with `message` parameter ONLY (no `target` parameter)
