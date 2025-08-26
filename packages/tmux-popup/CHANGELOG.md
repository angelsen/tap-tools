# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed
- Filter component now properly displays dict options (only labels, not "label: value")

### Removed

## [0.2.1] - 2025-08-25

### Added

### Changed

### Fixed

### Removed

## [0.2.0] - 2025-08-16

### Added
- Canvas component for rich content display
- Row and Column layout components
- Markdown content with code block support
- Text content component
- Comprehensive examples (display.py, input.py, combined.py)
- Core Concepts documentation section
- Debug mode for viewing generated scripts
- Full gum passthrough support via kwargs
- Type hints with base classes
- llms.txt quick reference

### Changed
- Complete API redesign with Popup → Canvas/Interactive → show() pattern
- Simplified to use Markdown for all formatted content including code
- Reorganized examples into three clear categories
- Streamlined README from 392 to 248 lines
- Better separation of display vs interactive components

### Fixed
- Layout calculations for borders and spacing
- Shell quoting in generated scripts

### Removed
- Code class (use Markdown code blocks instead)
- Old demo.py and flask_demo.py examples
- Complex gum module structure

## [0.1.2] - 2025-08-13

### Added
- Changelog tracking with relkit support

### Changed

### Fixed

### Removed

## [0.1.1] - 2025-08-11

### Initial Release
- Composable tmux popup system with gum UI components
- Support for various gum components (choose, input, confirm, etc.)
- Flexible positioning and sizing options
- Published to PyPI as public package
