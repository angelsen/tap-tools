# Tool installation helper
.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Usage:"
	@echo "  make tool-install PKG=termtap  # Install tool with stable PyPI deps"
	@echo ""
	@echo "For development, use: uv run termtap"

.PHONY: tool-install
tool-install:
	uv tool install packages/$(PKG) --no-sources --force