"""Generate Pydantic models from HTTP request/response bodies."""

import json
from datamodel_code_generator import generate, InputFileType, DataModelType
from webtap.app import app
from webtap.commands._builders import success_response, error_response
from webtap.commands._code_generation import (
    ensure_output_directory,
    parse_json,
    extract_json_path,
    validate_generation_data,
)
from webtap.commands._utils import evaluate_expression, fetch_body_content
from webtap.commands._tips import get_mcp_description


mcp_desc = get_mcp_description("to_model")


@app.command(display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": mcp_desc or ""})
def to_model(
    state,
    id: int,
    output: str,
    model_name: str,
    field: str = "response.content",
    json_path: str = None,  # pyright: ignore[reportArgumentType]
    expr: str = None,  # pyright: ignore[reportArgumentType]
) -> dict:  # pyright: ignore[reportArgumentType]
    """Generate Pydantic model from request or response body.

    Args:
        id: Row ID from network() output
        output: Output file path for generated model (e.g., "models/user.py")
        model_name: Class name for generated model (e.g., "User")
        field: Body to use - "response.content" (default) or "request.postData"
        json_path: Optional JSON path to extract nested data (e.g., "data[0]")
        expr: Optional Python expression to transform data (has 'body' variable)

    Examples:
        to_model(5, "models/user.py", "User")
        to_model(5, "models/user.py", "User", json_path="data[0]")
        to_model(5, "models/form.py", "Form", field="request.postData")
        to_model(5, "models/clean.py", "Clean", expr="{k: v for k, v in json.loads(body).items() if k != 'meta'}")

    Returns:
        Success message with generation details
    """
    # Get HAR entry via RPC - need full entry with request_id for body fetch
    try:
        result = state.client.call("request", id=id, fields=["*"])
        har_entry = result.get("entry")
    except Exception as e:
        return error_response(f"Failed to get request: {e}")

    if not har_entry:
        return error_response(f"Request {id} not found")

    # Fetch body content
    body_content, err = fetch_body_content(state, har_entry, field)
    if err or body_content is None:
        return error_response(
            err or "Failed to fetch body",
            suggestions=[
                f"Field '{field}' could not be fetched",
                "For response body: field='response.content'",
                "For POST data: field='request.postData'",
            ],
        )

    # Transform via expression or parse as JSON
    if expr:
        try:
            namespace = {"body": body_content}
            data, _ = evaluate_expression(expr, namespace)
        except Exception as e:
            return error_response(
                f"Expression failed: {e}",
                suggestions=[
                    "Variable available: 'body' (str)",
                    "Example: json.loads(body)['data'][0]",
                    "Example: dict(urllib.parse.parse_qsl(body))",
                ],
            )
    else:
        if not body_content.strip():
            return error_response("Body is empty")

        data, parse_err = parse_json(body_content)
        if parse_err:
            return error_response(
                parse_err,
                suggestions=[
                    "Body must be valid JSON, or use expr to transform it",
                    'For form data: expr="dict(urllib.parse.parse_qsl(body))"',
                ],
            )

    # Extract nested path if specified
    if json_path:
        data, err = extract_json_path(data, json_path)
        if err:
            return error_response(
                err,
                suggestions=[
                    f"Path '{json_path}' not found in body",
                    'Try a simpler path like "data" or "data[0]"',
                ],
            )

    # Validate structure
    is_valid, validation_err = validate_generation_data(data)
    if not is_valid:
        return error_response(
            validation_err or "Invalid data structure",
            suggestions=[
                "Code generation requires dict or list structure",
                "Use json_path or expr to extract a complex object",
            ],
        )

    # Ensure output directory exists
    output_path = ensure_output_directory(output)

    # Generate model
    try:
        generate(
            json.dumps(data),
            input_file_type=InputFileType.Json,
            input_filename="response.json",
            output=output_path,
            output_model_type=DataModelType.PydanticV2BaseModel,
            class_name=model_name,
            snake_case_field=True,
            use_standard_collections=True,
            use_union_operator=True,
        )
    except Exception as e:
        return error_response(
            f"Model generation failed: {e}",
            suggestions=[
                "Check that the JSON structure is valid",
                "Try simplifying with json_path",
                "Ensure output directory is writable",
            ],
        )

    # Count fields
    try:
        model_content = output_path.read_text()
        field_count = model_content.count(": ")
    except Exception:
        field_count = "unknown"

    return success_response(
        "Model generated successfully",
        details={
            "Class": model_name,
            "Output": str(output_path),
            "Fields": field_count,
            "Size": f"{output_path.stat().st_size} bytes",
        },
    )
