# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [0.1.4] - 2025-09-08

### Added
- Request timeout handling (3 seconds) in Chrome extension for better error detection
- Comprehensive `cleanup()` method for proper resource management on exit
- `atexit` registration to ensure cleanup happens even on unexpected termination

### Changed
- **API Consolidation**: Merged `/pages` and `/instance` endpoints into single `/info` endpoint
- Enhanced `/status` endpoint to include fetch details inline (eliminates separate API call)
- Improved error messages in extension to distinguish between timeout, server not running, and other failures
- API server shutdown now uses `asyncio.run()` for proper task cleanup

### Fixed
- Graceful shutdown issue that left zombie tasks with "Task was destroyed but it is pending" error
- API server cleanup on application exit now properly cancels all async tasks
- Extension error handling now provides specific feedback for different failure modes

### Removed
- `/instance` endpoint (functionality merged into `/info`)
- `/fetch/paused` endpoint (data now included in `/status` response)

## [0.1.3] - 2025-09-05

### Added
- Multi-instance WebTap support with first-come-first-serve port management
- `/instance` endpoint to show WebTap instance information (PID, connected page, events)
- `/release` endpoint for graceful API port handoff between instances
- Chrome extension "Switch WebTap Instance" button for managing multiple instances
- Instance status display in extension popup showing PID and event count
- Automatic reconnection in extension after instance switching

### Changed
- API server now checks port availability before starting (port 8765)
- Chrome profile launch strategy uses bindfs mounting instead of symlinks
- Service docstrings simplified (removed redundant "Internal service for" prefixes)
- Added `api_thread` tracking to WebTapState for proper thread lifecycle management

### Fixed
- SQL numeric comparisons in query builder now use string comparison instead of CAST
- Type annotations improved with proper union types (`threading.Thread | None`)
- Network service HTTP status filtering uses string comparison to prevent SQL errors
- Extension connection handling during instance transitions

### Removed

## [0.1.2] - 2025-09-05

### Added

### Changed

### Fixed

### Removed

## [0.1.1] - 2025-09-05

### Added

### Changed

### Fixed

### Removed

## [0.1.0] - 2025-09-05

### Added
- Chrome DevTools Protocol (CDP) integration for browser debugging
- Native CDP Storage architecture using DuckDB for event storage
- Dynamic field discovery with fuzzy matching across all CDP events
- Network request/response monitoring with on-demand body fetching
- Console message capture with error tracking
- JavaScript execution in browser context via `js()` command
- Request interception and modification via `fetch()` command
- Chrome extension for visual page selection and debugging
- Bootstrap commands for downloading filters and extension (`setup-filters`, `setup-extension`)
- Chrome launcher command (`launch-chrome`) for debugging-enabled browser startup
- FastAPI server on port 8765 for Chrome extension integration
- Comprehensive filter system (ads, tracking, analytics, CDN, consent, monitoring)
- Events query system for flexible CDP event exploration
- Inspect command with Python environment for data analysis
- Svelte Debug Protocol (SDP) experimental support for Svelte app debugging
- Service layer architecture with clean dependency injection
- Markdown-based output formatting for all commands
- MCP (Model Context Protocol) support via ReplKit2
- CLI mode with Typer integration

### Changed
- **BREAKING**: Removed single `bootstrap` command, replaced with separate setup commands
- **BREAKING**: `eval()` and `exec()` commands replaced by unified `js()` command
- **BREAKING**: All commands now return markdown dictionaries instead of plain text
- Aligned with ReplKit2 v0.11.0 API changes (`typer_config` instead of `cli_config`)
- Store CDP events as-is without transformation (Native CDP Storage philosophy)
- Connection errors return error responses instead of raising exceptions
- Standardized command pattern with unified builders and error handling

### Fixed
- CLI mode parameter handling for dict/list types
- Type checking errors with proper null checks
- Import order issues in CLI mode
- Shell completion options properly hidden in CLI mode

<!-- 
When you run 'relkit bump', the [Unreleased] section will automatically 
become the new version section. Make sure to add your changes above!
-->
