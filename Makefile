# Code Convention Conformance using Claude Code

SHELL := /bin/bash
.PHONY: conform-module conform-file conform-shell format

# Conform Python module to conventions
conform-module:
	@echo "Conforming module $(TARGET) to Python conventions..."
	@PROMPT=$$(cat .prompts/conventions/python-module.prompt | sed "s|\$$(MODULE)|$(TARGET)|g") && \
	claude --model sonnet -p "$$PROMPT" \
	--add-dir $(TARGET) \
	--allowedTools "Read" "Edit" "MultiEdit" "Grep" "Glob"

# Conform Python file to conventions
conform-file:
	@echo "Conforming file $(TARGET) to Python conventions..."
	@PROMPT=$$(cat .prompts/conventions/python-file.prompt | sed "s|\$$(FILE)|$(TARGET)|g") && \
	claude --model sonnet -p "$$PROMPT" \
	--add-dir $$(dirname $(TARGET)) \
	--allowedTools "Read" "Edit" "MultiEdit" "Grep" "Glob"

# Conform shell script to conventions
conform-shell:
	@echo "Conforming script $(TARGET) to shell conventions..."
	@PROMPT=$$(cat .prompts/conventions/shell-script.prompt | sed "s|\$$(SCRIPT)|$(TARGET)|g") && \
	claude --model sonnet -p "$$PROMPT" \
	--add-dir $$(dirname $(TARGET)) \
	--allowedTools "Read" "Edit"

# Format both Python and shell files in a directory
format:
	@echo "Formatting Python files in $(TARGET)..."
	@uv run ruff format $(TARGET)
	@echo "Formatting shell scripts in $(TARGET)..."
	@find $(TARGET) -type f \( -name "*.sh" -o -name "*.bash" \) -exec sh -c 'echo "Formatting {}" && shfmt -w "{}"' \;