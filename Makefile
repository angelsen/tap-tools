# Tool installation helper
.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Usage:"
	@echo "  make tool-install PKG=termtap   # Install tool with stable PyPI deps"
	@echo "  make format-web PKG=webtap      # Format JS/HTML/JSON with prettier"
	@echo ""
	@echo "For development, use: uv run termtap"

.PHONY: tool-install
tool-install:
	uv tool install packages/$(PKG) --no-sources --force

.PHONY: format-web
format-web:
	@git ls-files packages/$(PKG) | grep -E '\.(js|html|json|css)$$' | xargs -r prettier --write