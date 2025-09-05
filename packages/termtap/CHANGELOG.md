# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

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
