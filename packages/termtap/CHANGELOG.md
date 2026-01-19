# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [0.13.0] - 2026-01-19

### Added
- `Pane.get()` unified API for pane content retrieval (stream if available, capture if not)
- Cancel action support: `cancel` RPC method, delete key binding in queue screen, `action_cancelled` event
- Busy state handling in actions: `READY_CHECK + busy` and `WATCHING + busy` capture output immediately
- OutputPane message-passing: `AddSelection`/`UndoSelection` messages for pattern selection
- FzfSelector action methods (`action_confirm()`, `action_cancel()`) with BINDINGS for footer display

### Changed
- Textual bindings modernized from `Binding()` to tuple format across all screens
- PatternScreen uses `VerticalScroll` with Footer outside scroll container
- FzfSelector uses `display` property instead of CSS classes for visibility
- Pane content access consolidated through `Pane.get()` instead of direct `pane.screen` calls

### Fixed
- Card and content panel overflow with `height: auto` and `overflow-y: auto`
- OutputPane minimum height constraint (`min-height: 10`)

### Removed
- Unused `mark_idx` field from buffer state reporting
- Placeholder `action_noop()` methods in screens

## [0.12.0] - 2026-01-16

### Added
- `termtap repl` subcommand for explicit REPL mode
- Pattern pairing system (link ready/busy patterns)
- Pattern lifecycle hooks (on_add, on_update, on_delete)
- LogoText widget with custom background rendering
- Background widget for gradient patterns
- Pattern editor screen in companion UI
- BaseTerminalPane for widget reuse
- Card builders for theme-aware layouts
- DaemonContext for dependency injection
- Client context system for session-aware operations

### Changed
- **BREAKING**: Default `termtap` invocation runs companion (TTY) or MCP (piped stdin)
- **BREAKING**: Removed `--mcp` flag (auto-detected via stdin)
- **BREAKING**: All commands use `pane_id` parameter (strict %format) instead of flexible `target`
- Daemon handlers extracted to modular `daemon/handlers/` directory
- Pattern matching returns metadata about which pattern matched
- Companion TCSS organized into 4 sections (tokens, containers, components, screens)

### Fixed
- LogoText whitespace now matches card background (explicit bgcolor in render_line)

### Removed
- YAML-based configuration system (config.py, CONFIG_PATH)

## [0.10.2] - 2025-12-17

### Added

### Changed

### Fixed
- Added `literal=True` to tmux send-keys calls to preserve special characters
  - Prevents shell metacharacters (`;`, `|`, `&`, etc.) from being interpreted as tmux key sequences
  - Applied to Python handler, base handler `before_send()`, and track command

### Removed

## [0.10.1] - 2025-10-05

### Added

### Changed

### Fixed
- Python handler now recognizes `poll_schedule_timeout.constprop.0` wait_channel on kernel 6.15+
  - Newer kernels use different polling function with compiler optimization suffix
  - Handler detects any `poll_schedule_timeout*` pattern as ready state
  - Resolves issue where Python REPL appeared stuck on Arch Linux with kernel 6.15.6

### Removed

## [0.10.0] - 2025-09-28

### Added

### Changed
- **BREAKING**: Updated to ReplKit2 v0.12.0 - using `mcp_config` instead of `fastmcp` parameter
- Minimum ReplKit2 version requirement updated from 0.11.0 to 0.12.0

### Fixed

### Removed

## [0.9.2] - 2025-09-19

### Added

### Changed
- Updated tmux-popup dependency to >=0.2.2

### Fixed

### Removed

## [0.9.1] - 2025-09-18

### Added

### Changed

### Fixed
- Fixed tmux pane listing when pane titles contain special characters (e.g., Windows paths with backslashes in SSH sessions)
  - Split tmux queries into two calls: one for JSON-safe fields, one for pane titles
  - Resolves issue where panes with Windows paths were silently skipped in `ls()` command

### Removed

## [0.9.0] - 2025-09-17

### Added
- New handler action types: `auto-ask` and `ask-ask` for more flexible confirmation patterns
  - `auto-ask`: Send command automatically, then ask when done
  - `ask-ask`: Ask before sending, then ask when done

### Changed
- **BREAKING**: Renamed `send_keys` command to `send_keystrokes` for better clarity
- **BREAKING**: Changed `send_keystrokes` parameter from `keys: str` to `keys: list[str]` for better MCP/LLM compatibility
- Enhanced `send_keystrokes` description with clear use cases and explicit guidance on when NOT to use it for shell commands
- Improved handler configuration flow control to support new action types

### Fixed

### Removed

## [0.8.1] - 2025-09-12

### Added
- Cross-platform support for macOS/BSD systems without `/proc` filesystem
- `_create_noproc_process()` function to create fallback ProcessNode instances
- Special "no_proc" wait_channel marker to identify processes on systems without /proc

### Changed
- Process tree functions now gracefully handle absence of /proc filesystem
- `ConfirmationHandler` now detects "no_proc" marker instead of checking filesystem directly
- All process operations return noproc ProcessNodes on macOS/BSD instead of failing

### Fixed
- Process tracking no longer crashes on macOS due to missing /proc filesystem
- `process_scan` context manager works on all platforms

### Removed

## [0.8.0] - 2025-09-12

### Added
- macOS and BSD support through confirmation handler (systems without /proc)

### Changed
- Renamed `_SSHHandler` to `_ConfirmationHandler` to handle both SSH and no-/proc systems

### Fixed

### Removed

## [0.7.0] - 2025-09-11

### Added
- Line ending configuration support in handlers.md (lf, crlf, cr, none)
- `LineEnding` enum for explicit line termination control
- Support for Windows SSH servers requiring CRLF line endings
- Deprecation warnings for legacy `enter` parameter

### Changed
- Handler configuration now accepts optional third parameter for line ending
- `send_keys` and `send_via_paste_buffer` use `line_ending` parameter instead of `enter`
- Auto-accepted commands now respect configured line endings

### Fixed

### Removed

## [0.6.2] - 2025-09-09

### Added

### Changed
- Improved handlers.md template with more comprehensive examples showing auto, ask, and never actions

### Fixed

### Removed

## [0.6.1] - 2025-09-09

### Added

### Changed

### Fixed
- Improved handler configuration initialization - handlers.md now created at startup
- Cleaner template with better instructions and syntax examples
- Fixed code duplication in __main__.py module

### Removed

## [0.6.0] - 2025-09-09

### Added
- Handler configuration system with markdown-based rules via `handlers.md` file
- Auto-accept, ask, and never actions for commands based on pattern matching
- Template method pattern for `before_send`/`after_send` hooks with configuration checking
- Automatic `handlers.md` template creation when missing

### Changed
- **BREAKING**: Handlers should now override `_before_send_impl` and `_after_send_impl` instead of `before_send` and `after_send` directly
- Applied Python naming conventions to internal handler module classes and functions

### Fixed

### Removed

## [0.5.1] - 2025-09-05

### Added

### Changed

### Fixed
- Exclude node_modules and .svelte-kit from source distribution (reduces size from 16MB to ~50KB)

### Removed

## [0.5.0] - 2025-09-05

### Added

### Changed
- **BREAKING**: Renamed `read` command to `pane` for better semantic clarity
- **BREAKING**: Updated to tmux-popup v0.2.1 API (requires tmux-popup >= 0.2.1)
- Migrated popup components from GumStyle/GumFilter/GumInput to Canvas/Markdown/Filter/Input
- Improved pane selection formatting with better column spacing
- Standardized all popups to width="65" for consistency
- Added interaction hints to `pane` command output showing available MCP commands for each pane

### Fixed
- Python handler now properly handles single-line compound statements (e.g., `for i in range(3): print(i)`)
- Python handler subprocess detection improved for async operations with Playwright
- Multi-select popup instructions corrected (Tab to select, not space)

### Removed

## [0.4.1] - 2025-08-14

### Added
- Published to PyPI for public availability
- Support for standard tool installation via `uv tool install` and `pipx`

### Changed
- Removed private classifier to enable PyPI publishing
- Updated installation documentation for PyPI distribution

### Fixed
<!-- Example: - Memory leak in worker process -->
<!-- Example: - Incorrect handling of UTF-8 file names -->

### Removed
<!-- Example: - Deprecated legacy API endpoints -->
<!-- Example: - Support for Python 3.7 -->

<!-- 
When you run 'relkit bump', the [Unreleased] section will automatically 
become the new version section. Make sure to add your changes above!
-->
