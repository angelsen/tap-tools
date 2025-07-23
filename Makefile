# Python Convention Enforcement using Claude Code

.PHONY: enforce-module

# Enforce conventions on a specific module
enforce-module:
	@echo "Enforcing conventions for $(MODULE)..."
	@claude -p "You are enforcing Python code conventions for module $(MODULE). \
	\
	CONTEXT: Code quality improves when internal implementation is clearly separated from public API. Consistent documentation helps developers understand and use the code correctly. \
	\
	TASK: Read the PUBLIC API list from $(MODULE)/__init__.py docstring. Any function NOT listed there should be internal. \
	\
	SPECIFIC ACTIONS: \
	1. Find the PUBLIC API list in the module docstring of $(MODULE)/__init__.py \
	2. For each Python file in the module: \
	   - Add underscore prefix to any function NOT in the PUBLIC API list \
	   - Ensure the file has a module docstring explaining its purpose within the module \
	   - Add docstrings to all public functions using this format: \
	     - First line: One-line summary ending with period \
	     - Blank line if more details needed \
	     - Args section if parameters exist \
	     - Returns section if non-None return \
	     - Raises section if exceptions are raised \
	3. Update $(MODULE)/__init__.py: \
	   - Set __all__ to match exactly the PUBLIC API list \
	   - Remove any underscore-prefixed items from imports/exports \
	4. Comments and documentation style: \
	   - Remove obvious comments like '# Import os' or '# Return result' \
	   - Keep only comments that explain WHY, not WHAT \
	   - Complex algorithms should have a comment explaining the approach \
	   - Public functions need complete docstrings, private functions need at least a one-line summary \
	\
	Make all necessary changes directly. Focus on semantic clarity - the code and documentation should clearly communicate intent and usage. \
	For maximum efficiency, analyze all files first, then make changes in parallel." \
	--add-dir $(MODULE)