# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

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
