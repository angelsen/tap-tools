# tap-tools workspace
SHELL := /bin/bash
.DEFAULT_GOAL := help

# Variables
PACKAGES := termtap webtap logtap

# Help
.PHONY: help
help:
	@echo "tap-tools development"
	@echo ""
	@echo "Development:"
	@echo "  dev-<pkg>     Run package REPL"
	@echo "  sync          Install dependencies"
	@echo ""
	@echo "Quality:"
	@echo "  format        Format code"
	@echo "  lint          Fix linting issues"
	@echo "  check         Type check"
	@echo ""
	@echo "Dependencies:"
	@echo "  add-dep-<pkg> DEP=name  Add dependency"
	@echo "  add-opt-<pkg> GROUP=g DEP=name  Add optional"
	@echo ""
	@echo "Release:"
	@echo "  check-<pkg>   Test build"
	@echo "  release-<pkg> Create release"

# Development
.PHONY: dev-termtap dev-webtap dev-logtap
dev-termtap:
	@uv run --package termtap termtap

dev-webtap:
	@uv run --package webtap webtap

dev-logtap:
	@uv run --package logtap logtap

.PHONY: sync
sync:
	@echo "→ Syncing dependencies..."
	@uv sync
	@echo "✓ Done"

# Quality
.PHONY: format lint check
format:
	@echo "→ Formatting code..."
	@uv run ruff format .
	@echo "✓ Done"

lint:
	@echo "→ Fixing lints..."
	@uv run ruff check . --fix
	@echo "✓ Done"

check:
	@echo "→ Type checking..."
	@basedpyright
	@echo "✓ Done"

# Dependencies
.PHONY: add-dep-%
add-dep-%:
	@if [ -z "$(DEP)" ]; then \
		echo "✗ Usage: make add-dep-$* DEP=package"; \
		exit 1; \
	fi
	@echo "→ Adding $(DEP) to $*..."
	@uv add --package $* $(DEP)
	@echo "✓ Done"

.PHONY: add-opt-%
add-opt-%:
	@if [ -z "$(GROUP)" ] || [ -z "$(DEP)" ]; then \
		echo "✗ Usage: make add-opt-$* GROUP=dev DEP=package"; \
		exit 1; \
	fi
	@echo "→ Adding $(DEP) to $* [$(GROUP)]..."
	@uv add --package $* --optional $(GROUP) $(DEP)
	@echo "✓ Done"

# Release
.PHONY: check-%
check-%:
	@if [ ! -d "packages/$*" ]; then \
		echo "✗ Package $* not found"; \
		exit 1; \
	fi
	@echo "→ Checking $* build..."
	@uv build --package $* --no-sources
	@echo "✓ Ready for distribution"

.PHONY: release-%
release-%:
	@if [ ! -d "packages/$*" ]; then \
		echo "✗ Package $* not found"; \
		exit 1; \
	fi
	@VERSION=$$(grep '^version' packages/$*/pyproject.toml | cut -d'"' -f2); \
	echo "→ Releasing $* v$$VERSION..."; \
	git tag -a $*-v$$VERSION -m "Release $* v$$VERSION"; \
	uv tool install packages/$*; \
	echo "✓ Tagged v$$VERSION"; \
	echo "  Push: git push origin $*-v$$VERSION"