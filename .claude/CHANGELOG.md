# Claude Agent & Command Changelog

## [2.1.0] - 2025-10-16

### Added
- **`/handoff` command**: Create handoff summaries and onboard next colleague
  - Generates structured summary with accomplishments, status, next steps
  - Sends onboarding message to colleague via `mcp__termtap__send`
  - Includes critical reminder about searching local resources before coding
  - Template includes example workflow and available project resources

### Impact
- Consistent handoff process across sessions
- Knowledge transfer is structured and complete
- New colleagues get immediate context and guidance

## [2.0.0] - 2025-09-05

### Changed
- **Major refactor**: Shifted from mechanical to context-aware convention enforcement
- **python-file-enforcer**: Now checks file context before applying underscores
  - Files starting with `_` don't get double-privatized
  - Functions in internal directories considered for clean names
- **python-module-enforcer**: Respects directory structure as organizational context
  - Services/utils directories no longer force underscore prefixes
  - Documentation requirements now match module purpose
- **analyze-apis**: Simplified PUBLIC API documentation requirements
  - Only true entry points need PUBLIC API sections
  - Internal modules get simple docstrings
- **All enforcement commands**: Added double-privatization prevention
  - conform, enforce-conventions, enforce-staged updated

### Added
- Context-aware examples showing good vs bad patterns
- Directory structure recognition (services/, utils/, internal/)
- Smart privacy rules based on file/directory context
- Principles section emphasizing thoughtful over mechanical application

### Fixed
- Double-privatization anti-pattern (e.g., `_utils.py` with `_function()`)
- Over-documentation of internal modules
- Excessive underscore prefixes in service classes

### Impact
- Cleaner, more Pythonic code
- Better readability without sacrificing clear boundaries
- Reduced cognitive overhead from unnecessary underscores

## [1.0.0] - 2025-08-07 (Approximate)

### Initial Version
- Basic Python convention enforcement agents
- Mechanical application of underscore prefixes
- PUBLIC API documentation for all modules
- Shell script safety enforcer
- Commands for staged files and comprehensive enforcement

### Principles (Original)
- Functions not in PUBLIC API get underscore prefix
- All modules require PUBLIC API documentation
- Strict enforcement of naming conventions
- File renaming to `_filename.py` for internal modules

### Known Issues (That Led to v2.0.0)
- Over-application of conventions
- Double-privatization patterns
- Redundant PUBLIC API sections in command files
- Mechanical compliance without considering context