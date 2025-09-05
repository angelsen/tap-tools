"""Shared utilities for WebTap command modules."""

import ast
import json
import sys
from io import StringIO
from typing import Any, Tuple


def evaluate_expression(expr: str, namespace: dict) -> Tuple[Any, str]:
    """Execute Python code and capture both stdout and the last expression result.

    Args:
        expr: Python code to execute.
        namespace: Dict of variables available to the code.
    """
    # Standard libraries - always available
    import re
    import base64
    import hashlib
    import html
    import urllib.parse
    import datetime
    import collections
    import itertools
    import pprint
    import textwrap
    import difflib
    import xml.etree.ElementTree as ElementTree

    # Web scraping & parsing
    from bs4 import BeautifulSoup
    import lxml.etree
    import lxml.html

    # Reverse engineering essentials
    import jwt
    import yaml
    import httpx
    import cryptography.fernet
    import cryptography.hazmat
    from google.protobuf import json_format as protobuf_json
    from google.protobuf import text_format as protobuf_text
    import msgpack

    # Update namespace with ALL libraries
    namespace.update(
        {
            # Standard
            "re": re,
            "json": json,  # Already imported at module level
            "base64": base64,
            "hashlib": hashlib,
            "html": html,
            "urllib": urllib,
            "datetime": datetime,
            "collections": collections,
            "itertools": itertools,
            "pprint": pprint,
            "textwrap": textwrap,
            "difflib": difflib,
            "ast": ast,  # Already imported at module level
            "ElementTree": ElementTree,
            "ET": ElementTree,  # Common alias
            # Web scraping
            "BeautifulSoup": BeautifulSoup,
            "bs4": BeautifulSoup,  # Alias
            "lxml": lxml,
            # Reverse engineering
            "jwt": jwt,
            "yaml": yaml,
            "httpx": httpx,
            "cryptography": cryptography,
            "protobuf_json": protobuf_json,
            "protobuf_text": protobuf_text,
            "msgpack": msgpack,
        }
    )

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    result = None

    try:
        # Parse the code to find if last node is an expression
        tree = ast.parse(expr)
        if tree.body:
            # If last node is an Expression, evaluate it separately
            if isinstance(tree.body[-1], ast.Expr):
                # Execute all but the last node
                if len(tree.body) > 1:
                    exec_tree = ast.Module(body=tree.body[:-1], type_ignores=[])
                    exec(compile(exec_tree, "<string>", "exec"), namespace)
                # Evaluate the last expression
                result = eval(compile(ast.Expression(body=tree.body[-1].value), "<string>", "eval"), namespace)
            else:
                # All statements, just exec everything
                exec(compile(tree, "<string>", "exec"), namespace)

    except SyntaxError:
        # Fallback to simple exec if parsing fails
        exec(expr, namespace)
    finally:
        # Always restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()

    return result, output


def format_expression_result(result: Any, output: str, max_length: int = 2000) -> str:
    """Format the result of an expression evaluation for display.

    Args:
        result: The evaluation result.
        output: Any stdout output captured.
        max_length: Maximum length before truncation.
    """
    parts = []

    if output:
        parts.append(output.rstrip())

    if result is not None:
        if isinstance(result, (dict, list)):
            formatted = json.dumps(result, indent=2)
            if len(formatted) > max_length:
                parts.append(formatted[:max_length] + f"\n... [truncated, {len(formatted)} chars total]")
            else:
                parts.append(formatted)
        elif isinstance(result, str) and len(result) > max_length:
            parts.append(result[:max_length] + f"\n... [truncated, {len(result)} chars total]")
        else:
            parts.append(str(result))

    return "\n".join(parts) if parts else "(no output)"


# ============= MCP Dict Parameter Utilities =============


# ============= MCP Dict Parameter Utilities =============


def parse_options(options: dict = None, defaults: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Parse options dict with defaults.

    Args:
        options: User-provided options dict.
        defaults: Default values dict.
    """
    if defaults is None:
        defaults = {}
    if options is None:
        return defaults.copy()

    result = defaults.copy()
    result.update(options)
    return result


def extract_option(options: dict, key: str, default=None, required: bool = False):
    """Extract single option from dict with validation.

    Args:
        options: Options dict to extract from.
        key: Key to extract.
        default: Default value if not found.
        required: Whether the key is required.
    """
    if options is None:
        if required:
            raise ValueError(f"Required option '{key}' not provided")
        return default

    if required and key not in options:
        raise ValueError(f"Required option '{key}' not provided")

    return options.get(key, default)


def validate_dict_keys(options: dict, allowed: set, required: set = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Validate dict has only allowed keys and all required keys.

    Args:
        options: Dict to validate.
        allowed: Set of allowed keys.
        required: Optional set of required keys.
    """
    if options is None:
        options = {}

    # Check for unknown keys
    unknown = set(options.keys()) - allowed
    if unknown:
        raise ValueError(f"Unknown options: {', '.join(sorted(unknown))}")

    # Check for required keys
    if required:
        missing = required - set(options.keys())
        if missing:
            raise ValueError(f"Missing required options: {', '.join(sorted(missing))}")

    return options


def extract_nested(options: dict, path: str, default=None):
    """Extract nested value from dict using dot notation.

    Args:
        options: Dict to extract from.
        path: Dot-separated path.
        default: Default value if path not found.
    """
    if options is None:
        return default

    current = options
    for key in path.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default

    return current
