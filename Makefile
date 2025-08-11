# tap-tools workspace
SHELL := /bin/bash
.DEFAULT_GOAL := help

# Package categories
TOOLS := termtap webtap logtap
LIBRARIES := tmux-popup
PACKAGES := $(TOOLS) $(LIBRARIES)

# Help
.PHONY: help
help:
	@echo "tap-tools development"
	@echo ""
	@echo "Development:"
	@echo "  dev-<pkg>       Run package REPL"
	@echo "  sync            Install dependencies"
	@echo ""
	@echo "Quality:"
	@echo "  format          Format code"
	@echo "  lint            Fix linting issues"
	@echo "  check           Type check"
	@echo ""
	@echo "Dependencies:"
	@echo "  add-dep-<pkg> DEP=name         Add dependency"
	@echo "  add-opt-<pkg> GROUP=g DEP=name Add optional"
	@echo ""
	@echo "Version:"
	@echo "  version-<pkg>   Show package version"
	@echo "  versions        Show all versions"
	@echo "  bump-<pkg> BUMP=patch|minor|major  Bump version"
	@echo ""
	@echo "Release:"
	@echo "  preflight-<pkg> Pre-release checks"
	@echo "  build-<pkg>     Build package"
	@echo "  test-build-<pkg> Test built package"
	@echo "  release-<pkg>   Tag release"
	@echo "  publish-<pkg>   Publish to PyPI"
	@echo "  full-release-<pkg> Complete workflow"
	@echo "  clean-<pkg>     Clean build artifacts"
	@echo ""
	@echo "Assets:"
	@echo "  gif SRC=path    Convert MP4 to optimized GIF"

# Development
.PHONY: dev-termtap dev-webtap dev-logtap dev-tmux-popup
dev-termtap:
	@uv run --package termtap termtap

dev-webtap:
	@uv run --package webtap webtap

dev-logtap:
	@uv run --package logtap logtap

dev-tmux-popup:
	@uv run --package tmux-popup python packages/tmux-popup/examples/demo.py

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

# Version Management
.PHONY: version-%
version-%:
	@VERSION=$$(grep '^version' packages/$*/pyproject.toml | cut -d'"' -f2); \
	echo "$*: $$VERSION"

.PHONY: versions
versions:
	@echo "Package versions:"
	@for pkg in $(PACKAGES); do \
		VERSION=$$(grep '^version' packages/$$pkg/pyproject.toml 2>/dev/null | cut -d'"' -f2 || echo "N/A"); \
		printf "  %-12s %s\n" "$$pkg:" "$$VERSION"; \
	done

.PHONY: bump-%
bump-%:
	@if [ -z "$(BUMP)" ]; then \
		echo "✗ Usage: make bump-$* BUMP=patch|minor|major"; \
		exit 1; \
	fi
	@echo "→ Bumping $* version ($(BUMP))..."
	@cd packages/$* && uv version --bump $(BUMP) --no-sync
	@VERSION=$$(grep '^version' packages/$*/pyproject.toml | cut -d'"' -f2); \
	echo "✓ Bumped to $$VERSION"

# Building & Testing
.PHONY: build-%
build-%:
	@if [ ! -d "packages/$*" ]; then \
		echo "✗ Package $* not found"; \
		exit 1; \
	fi
	@echo "→ Building $* package..."
	@uv build --package $* --no-sources --out-dir packages/$*/dist
	@echo "✓ Built in packages/$*/dist/"

.PHONY: test-build-%
test-build-%:
	@if [ ! -d "packages/$*/dist" ]; then \
		echo "✗ No build found. Run 'make build-$*' first"; \
		exit 1; \
	fi
	@echo "→ Testing $* build..."
	@WHEEL=$$(ls packages/$*/dist/*.whl 2>/dev/null | head -1); \
	if [ -z "$$WHEEL" ]; then \
		echo "✗ No wheel found for $*"; \
		exit 1; \
	fi; \
	MODULE=$$(echo $* | tr '-' '_'); \
	uv run --with $$WHEEL --no-project -- python -c "import $$MODULE; print('✓ Import successful')"

# Pre-flight Checks
.PHONY: preflight-%
preflight-%:
	@echo "→ Pre-flight checks for $*..."
	@echo -n "  Package exists: "; \
	[ -d "packages/$*" ] && echo "✓" || (echo "✗" && exit 1)
	@echo -n "  Build system: "; \
	grep -q '^\[build-system\]' packages/$*/pyproject.toml && echo "✓" || echo "✗"
	@echo -n "  Not private: "; \
	! grep -q "Private :: Do Not Upload" packages/$*/pyproject.toml && echo "✓" || echo "⚠️  (marked private)"
	@echo -n "  Has README: "; \
	[ -f packages/$*/README.md ] && echo "✓" || echo "✗"
	@echo -n "  Version: "; \
	grep '^version' packages/$*/pyproject.toml | cut -d'"' -f2

# Release Management
.PHONY: release-%
release-%:
	@if [ ! -d "packages/$*" ]; then \
		echo "✗ Package $* not found"; \
		exit 1; \
	fi
	@VERSION=$$(grep '^version' packages/$*/pyproject.toml | cut -d'"' -f2); \
	echo "→ Releasing $* v$$VERSION..."; \
	git tag -a $*-v$$VERSION -m "Release $* v$$VERSION"; \
	if echo "$(TOOLS)" | grep -qw "$*"; then \
		echo "  Installing tool locally..."; \
		uv tool install packages/$* --force; \
		echo "✓ Installed $* as tool"; \
	elif echo "$(LIBRARIES)" | grep -qw "$*"; then \
		echo "  Library package (not installing as tool)"; \
	fi; \
	echo "✓ Tagged $*-v$$VERSION"; \
	echo ""; \
	echo "Next steps:"; \
	echo "  git push origin $*-v$$VERSION"

# Publishing
.PHONY: publish-%
publish-%:
	@if [ ! -d "packages/$*" ]; then \
		echo "✗ Package $* not found"; \
		exit 1; \
	fi
	@if [ ! -d "packages/$*/dist" ]; then \
		echo "✗ No build found. Run 'make build-$*' first"; \
		exit 1; \
	fi
	@echo "→ Publishing $* to PyPI..."
	@cd packages/$* && uv publish --token "$$(pass pypi/uv-publish)"
	@echo "✓ Published to PyPI"

# Full Release Workflow
.PHONY: full-release-%
full-release-%: preflight-% build-% test-build-%
	@echo ""
	@echo "✓ Package $* ready for release!"
	@echo ""
	@echo "Complete the release:"
	@echo "  1. make release-$*     # Create git tag"
	@echo "  2. make publish-$*     # Publish to PyPI"
	@echo "  3. git push origin && git push origin --tags"

# Clean build artifacts
.PHONY: clean-%
clean-%:
	@rm -rf packages/$*/dist
	@echo "✓ Cleaned $* build artifacts"

# Assets
.PHONY: gif
gif:
	@if [ -z "$(SRC)" ]; then \
		echo "✗ Usage: make gif SRC=path/to/video.mp4"; \
		exit 1; \
	fi
	@if [ ! -f "$(SRC)" ]; then \
		echo "✗ File not found: $(SRC)"; \
		exit 1; \
	fi
	@OUTPUT=$$(echo "$(SRC)" | sed 's/\.mp4$$/.gif/' | sed 's/raw/processed/'); \
	echo "→ Converting $(SRC) to $$OUTPUT..."; \
	mkdir -p $$(dirname "$$OUTPUT"); \
	ffmpeg -i "$(SRC)" \
		-vf "fps=3,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=16:stats_mode=diff[p];[s1][p]paletteuse=dither=none:diff_mode=rectangle" \
		"$$OUTPUT" -y -loglevel error; \
	SIZE=$$(ls -lh "$$OUTPUT" | awk '{print $$5}'); \
	echo "✓ Created $$OUTPUT ($$SIZE)"