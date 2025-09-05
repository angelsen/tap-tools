# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

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
