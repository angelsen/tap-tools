# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [0.8.1] - 2025-10-16

### Added

### Changed

### Fixed
- **Extension setup**: Added missing `background.js` to downloaded extension files (setup-extension command now downloads all 5 required files)

### Removed

## [0.8.0] - 2025-10-16

### Added
- **quicktype command**: Generate types for TypeScript, Go, Rust, Python, and 10+ languages from request/response bodies
  - Auto-detects language from file extension (.ts, .go, .rs, etc.)
  - Supports all quicktype CLI options via `options` dict parameter
  - Language-aware header comments with event metadata
  - Supports `expr` and `json_path` for data transformation
- **Request body support**: `body()` and `to_model()` now work with POST/PUT/PATCH requests
  - Auto-detects `Network.requestWillBeSent` events and fetches POST data
  - Returns event data for `expr` evaluation on any CDP event type
- **Code generation utilities**: New `_code_generation.py` module with shared transformation functions
  - `parse_json()`, `extract_json_path()`, `validate_generation_data()`, `ensure_output_directory()`
- **BodyService.prepare_for_generation()**: Orchestrator method reducing duplication (2 queries → 1, 166 duplicate lines → 0)
- **Extension reload button**: Manual page list refresh for when auto-refresh doesn't update
- **Tips system**: Added contextual tips to `page()` and `pages()` commands from TIPS.md
- **Response builders**: `info_response()` now supports `tips` parameter (matches `table_response()`)
- **Extension UI**: Context menu for switching between sidepanel and popup window modes
- **Background service worker**: Manages UI mode switching and sidepanel close functionality

### Changed
- **State management**: Immutable snapshot architecture for thread-safe SSE broadcasting
  - New `StateSnapshot` frozen dataclass with atomic updates
  - `WebTapService._create_snapshot()` and `_trigger_broadcast()` replace direct broadcasts
  - All service mutations trigger snapshot updates via RLock-protected operations
- **CDPSession lifecycle**: DB thread now persists across connections (only dies on app exit)
  - `disconnect()` preserves DB thread and events for reconnection
  - New `cleanup()` method for proper app exit (stops DB thread)
  - Added `atexit` hook for automatic cleanup on process termination
  - Events persist across disconnect/reconnect cycles (cleared only by Clear button or exit)
- **Unexpected disconnect handling**: Preserves events for debugging instead of clearing
  - `_handle_unexpected_disconnect()` no longer calls `clear_events()`
  - Enhanced error messages for None close codes
- **Service layer**: Broadcast queue ownership moved to `WebTapService` with callback pattern
  - `DOMService` and `FetchService` now use `_broadcast_callback` instead of direct queue access
- **Extension safety**: All dynamic HTML uses safe DOM creation instead of `innerHTML`
  - New `showError()` and `showMessage()` helpers with auto-escaping
  - Replaced UTF-8 cross (✕) with pure CSS icon
- **to_model command**: Refactored to use `body_service.prepare_for_generation()` (170 → 85 lines)
  - Added `expr` parameter for custom transformations
  - Parameter renamed from `response` to `event`
- **body command**: Renamed internal `get_response_body()` to `get_body()` with auto-detection
  - Parameter renamed from `response` to `event`

### Fixed
- **Critical reconnection bug**: Page crashes now allow immediate reconnection
  - `CDPSession._on_close()` clears `ws_app` and `page_info` state after detecting unexpected disconnect
  - Previously "Already connected" error prevented reconnection after page kill
- **Error messages**: Fixed "Connection closed unexpectedly (code None)" → "Connection lost (page closed or crashed)"
- **Extension concurrency**: Added global operation lock to prevent concurrent button operations
- **SSE error handling**: Shows reconnect button instead of generic error message

### Removed

## [0.7.1] - 2025-10-12

### Added

### Changed

### Fixed
- **CRITICAL: DuckDB thread safety** - Fixed malloc corruption crashes during browsing
  - Implemented dedicated database thread with queue-based communication pattern
  - All database operations now serialized through single thread (WebSocket, FastAPI, REPL threads)
  - Fixed `WebTapService.event_count` property bypassing queue protection
  - Resolved "malloc(): unaligned tcache chunk detected" segfaults
  - Pattern: All threads → `_db_execute()` → queue → `_db_worker` thread → DuckDB

### Removed

## [0.7.0] - 2025-10-10

### Added

### Changed
- **BREAKING**: `to_model()` now requires `model_name` parameter for explicit class naming
  - Old: `to_model(123, "models/product.py", json_path="Data[0]")`
  - New: `to_model(123, "models/product.py", "Product", json_path="Data[0]")`
  - Enforces best practice: always specify what you're generating

### Fixed

### Removed

## [0.6.0] - 2025-10-10

### Added
- **to_model command**: Generate Pydantic v2 models from JSON response bodies using datamodel-codegen
  - Supports `json_path` parameter for extracting nested objects (e.g., `"Data[0]"`)
  - Auto-applies snake_case fields and modern type hints (`list`, `dict`, `| None`)
  - Perfect for reverse engineering APIs - inspect with `body()`, generate models with `to_model()`
- **datamodel-code-generator dependency**: Added for Python-native model generation (no subprocess)

### Changed
- **TIPS.md**: Added `to_model` cross-references in `body` and `network` tips

### Fixed

### Removed

## [0.5.2] - 2025-10-09

### Added

### Changed

### Fixed
- **setup-extension**: Update to download new side panel files (content.js, sidepanel.html, sidepanel.js) instead of old popup files
- **setup-extension --force**: Now properly cleans old extension directory before downloading new files
- **selections() command**: Updated error message to reference "side panel" instead of "popup"

### Removed

## [0.5.1] - 2025-10-09

### Added
- **js() persist parameter**: New `persist` parameter to control variable scope across calls (default: False)

### Changed
- **js() default scope**: Fresh scope by default (IIFE wrapping) to prevent const/let redeclaration errors
- **js() selection wrapping**: Selection parameter always uses fresh scope to avoid element redeclaration

### Fixed
- **js() redeclaration errors**: Fixed "Identifier 'element' has already been declared" when using selection parameter multiple times
- **js() const/let errors**: Fixed redeclaration errors when running multiple js() calls with const/let

### Removed

## [0.5.0] - 2025-10-09

### Added
- **Real-time SSE streaming**: API endpoint `/events` for Server-Sent Events broadcasting full state to extension
- **Element selection**: CDP-native `Overlay.setInspectMode` with visual badges on page
  - New `DOMService` for element inspection via CDP
  - `selections()` command for viewing selected elements with preview and data extraction
  - `content.js` for badge rendering on page
  - Thread-safe selection processing via background ThreadPoolExecutor
  - Auto-clear selections on disconnect and frame navigation
- **Error state management**: Persistent error banner in extension with dismiss endpoint `/errors/dismiss`
- **Broadcast queue**: Cross-thread signaling from WebSocket thread → FastAPI event loop via `asyncio.Queue`
- **Progress indicators**: Extension shows pending count during async element selection
- **Auto-refresh**: Page list updates on tab activate/create/remove/move events
- **CDP event callbacks**: `register_event_callback()` system for real-time event handling
- **js() element integration**: New `selection` parameter to run JavaScript on selected elements

### Changed
- **Extension architecture**: Migrated from popup (popup.html/popup.js) to side panel (sidepanel.html/sidepanel.js)
- **State propagation**: Replaced 2-second polling with SSE streaming (<100ms latency vs 2s worst-case)
- **API server**: Hybrid REST + SSE architecture with broadcast processor and graceful SSE client shutdown
- **Page list**: Increased size from 6 to 15 rows, auto-highlights connected page
- **CDP session**: Increased ping timeout from 10s to 20s, added 1-second debounce on event broadcasts
- **Response builders**: Consolidated `_errors.py` functionality into `_builders.py` with enhanced helpers
- **Cleanup flow**: `app.cleanup()` now calls `service.disconnect()` for proper state cleanup
- **Thread safety**: All blocking CDP calls in API endpoints wrapped in `asyncio.to_thread()`
- **Queue initialization**: Uses `threading.Event` for synchronization instead of sleep

### Removed
- **popup.html** and **popup.js**: Replaced by side panel architecture
- **_errors.py**: Merged into `_builders.py` for cleaner response builder consolidation
- **2-second polling**: Extension no longer polls `/status` endpoint

## [0.4.0] - 2025-09-28

### Added
- Filter mode support: `include` and `exclude` modes for fine-grained request filtering
- TypedDict for filter configuration ensuring type safety
- Filter tip in `network()` command showing example usage
- Markdown table display for filter categories replacing code blocks
- CDP resource types documentation in filter command

### Changed
- **BREAKING**: Filter categories now require explicit `mode` field ("include" or "exclude")
- **BREAKING**: Updated to ReplKit2 v0.12.0 - using `mcp_config` instead of `fastmcp` parameter
- Filter core returns data (`get_categories_summary()`) instead of formatted strings
- Presentation logic moved from FilterManager to command layer
- Server command uses assistant prefill to prevent LLM commentary

### Fixed
- Alert element in network command now uses correct `message` field instead of `content`
- Type annotations for optional parameters properly use `str | None`

### Removed
- Backward compatibility for filters without mode field
- Emoji icons in filter display, using plain text indicators instead

## [0.3.0] - 2025-09-19

### Added
- New `server` command for explicit API server management (start/stop/restart/status)
- Server command implemented as MCP prompt returning markdown status information

### Changed
- **BREAKING**: API server no longer starts automatically - must be started explicitly with `server('start')`
- API server management is now explicit and user-controlled

### Fixed

### Removed
- Automatic API server startup on webtap launch
- `/release` endpoint from API (no longer needed with explicit server management)

## [0.2.4] - 2025-09-19

### Added
- New `server` command for explicit API server management (start/stop/restart/status)
- Server command implemented as MCP prompt returning markdown status information

### Changed
- API server no longer starts automatically - must be started explicitly with `server('start')`
- API server management is now explicit and user-controlled

### Fixed

### Removed
- Automatic API server startup on webtap launch
- `/release` endpoint from API (no longer needed with explicit server management)

## [0.2.3] - 2025-09-12

### Added

### Changed
- Refactored inline strings to constants in setup services for better maintainability
- Extracted all script templates, paths, and configuration values as module-level constants

### Fixed

### Removed

## [0.2.2] - 2025-09-12

### Added

### Changed

### Fixed
- macOS Chrome Debug.app now launches Chrome directly to avoid Rosetta warnings on Apple Silicon
- Added LSArchitecturePriority to Info.plist for native architecture support

### Removed

## [0.2.1] - 2025-09-12

### Added

### Changed

### Fixed
- Chrome wrapper on macOS now includes `--remote-allow-origins='*'` flag to allow WebSocket connections
- All Chrome wrappers (Linux standard, Linux bindfs, macOS) now consistently include the flag
- Removed incorrect Linux-specific instructions from setup-desktop command output on macOS
- Fixed setup-chrome usage instructions to correctly reference `chrome-debug` instead of `google-chrome-stable`

### Removed

## [0.2.0] - 2025-09-12

### Added
- Cross-platform support (Linux and macOS)
- `setup-cleanup` command to identify and remove old WebTap installations
- `--bindfs` flag for `setup-chrome` to mount real Chrome profile for debugging (Linux only)
- Unified `chrome-debug` wrapper at `~/.local/bin/chrome-debug`
- Separate Chrome Debug launcher (doesn't override system Chrome)
- Platform detection with XDG-compliant paths via platformdirs

### Changed
- Chrome wrapper location from `~/.local/bin/wrappers/google-chrome-stable` to `~/.local/bin/chrome-debug`
- Desktop entry from `google-chrome.desktop` override to separate `chrome-debug.desktop`
- Extension location to platform-appropriate data directories
- Setup service refactored into platform-aware modules

### Fixed
- Cleanup command now detects all old installation locations

### Removed

## [0.1.5] - 2025-09-10

### Added
- New `setup-desktop` command to install desktop entry for GUI Chrome integration
- Desktop entry installation that overrides system Chrome launcher to use debug wrapper
- Automatic detection and modification of system Chrome desktop files

### Changed
- Refactored setup service from monolithic file into modular components
- Split `services/setup.py` into separate modules: `filters.py`, `extension.py`, `chrome.py`, `desktop.py`
- Updated type hints to use modern Python 3.9+ style (`dict` instead of `Dict`)

### Fixed
- Code style issues across setup modules (imports, formatting, type hints)

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
