# tap-tools workspace management
SHELL := /bin/bash

# Development shortcuts
.PHONY: dev-termtap dev-webtap dev-logtap
dev-termtap:
	@uv run --package termtap termtap

dev-webtap:
	@uv run --package webtap webtap

dev-logtap:
	@uv run --package logtap logtap

# Generic release template
# Usage: make release-termtap, make release-webtap, etc.
.PHONY: release-%
release-%:
	@if [ ! -d "packages/$*" ]; then \
		echo "Error: Package $* not found in packages/"; \
		exit 1; \
	fi
	@VERSION=$$(grep '^version = ' packages/$*/pyproject.toml | cut -d'"' -f2); \
	echo "Releasing $* v$$VERSION..."; \
	git tag -a $*-v$$VERSION -m "Release $* v$$VERSION"; \
	uv tool install packages/$*; \
	echo "✓ Tagged and installed $* v$$VERSION"; \
	echo "✓ Now '$*' runs the released version"; \
	echo "Push with: git push origin $*-v$$VERSION"

# Workspace operations
.PHONY: sync format lint check

sync:
	@echo "Syncing workspace dependencies..."
	@uv sync

format:
	@uv run ruff format .

lint:
	@uv run ruff check . --fix

check:
	@basedpyright