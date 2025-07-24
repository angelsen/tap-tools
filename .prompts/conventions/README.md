# Convention Templates

This directory contains prompts for conforming code to project conventions.

## Available Templates

- **python-module.prompt** - For Python modules with `__init__.py`
  - Applies underscore prefixes based on PUBLIC API
  - Standardizes docstrings and comments
  - Updates imports and exports

- **python-file.prompt** - For standalone Python files
  - Handles app-level files without module structure
  - Prefixes helper functions while keeping commands public
  - Applies appropriate docstring templates

- **shell-script.prompt** - For shell scripts
  - Enforces shell best practices
  - Adds proper quoting and error handling
  - Standardizes function naming

## Usage

```bash
make conform-module TARGET=packages/mypackage/src/mymodule
make conform-file TARGET=src/app.py
make conform-shell TARGET=scripts/deploy.sh
```

## Philosophy

These templates help maintain consistent code style by:
- Clearly separating public APIs from internal implementation
- Applying comprehensive documentation standards
- Following Python and shell best practices
- Preserving functionality while improving clarity