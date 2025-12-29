"""Shared utilities for WebTap command modules."""

import ast
import base64
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


# ============= Body Content Utilities =============


def fetch_body_content(state, har_entry: dict, field: str) -> tuple[str | None, str | None]:
    """Fetch body content based on field selector.

    Args:
        state: WebTap state with client (RPC client).
        har_entry: HAR entry from request_details().
        field: Field selector ("response.content" or "request.postData").

    Returns:
        Tuple of (body_content, error_message).
    """
    if field == "response.content":
        request_id = har_entry.get("request_id")
        if not request_id:
            return None, "No request_id in HAR entry"

        try:
            cdp_result = state.client.call("cdp", command="Network.getResponseBody", params={"requestId": request_id})
            result = cdp_result.get("result", {})
        except Exception as e:
            return None, f"Failed to fetch response body: {e}"

        if not result:
            return None, "Failed to fetch response body"

        body = result.get("body", "")
        if result.get("base64Encoded"):
            try:
                body = base64.b64decode(body).decode("utf-8")
            except Exception as e:
                return None, f"Failed to decode base64 body: {e}"

        return body, None

    elif field == "request.postData":
        post_data = har_entry.get("request", {}).get("postData", {})
        text = post_data.get("text")
        if not text:
            return None, "No POST data in request"
        return text, None

    else:
        return None, f"Unknown field: {field}. Use 'response.content' or 'request.postData'"
