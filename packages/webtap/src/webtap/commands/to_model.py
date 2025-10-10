"""Generate Pydantic models from HTTP response bodies."""

import json
from pathlib import Path
from datamodel_code_generator import generate, InputFileType, DataModelType
from webtap.app import app
from webtap.commands._builders import check_connection, success_response, error_response
from webtap.commands._tips import get_mcp_description


mcp_desc = get_mcp_description("to_model")


@app.command(display="markdown", fastmcp={"type": "tool", "description": mcp_desc} if mcp_desc else {"type": "tool"})
def to_model(state, response: int, output: str, json_path: str = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Generate Pydantic model from response body using datamodel-codegen.

    Args:
        response: Response row ID from network() table
        output: Output file path for generated model (e.g., "models/product.py")
        json_path: Optional JSON path to extract nested data (e.g., "Data[0]")

    Returns:
        Success message with generation details
    """
    if error := check_connection(state):
        return error

    # Get response body from service
    body_service = state.service.body
    result = body_service.get_response_body(response, use_cache=True)

    if "error" in result:
        return error_response(result["error"])

    body_content = result.get("body", "")
    is_base64 = result.get("base64Encoded", False)

    # Decode if needed
    if is_base64:
        decoded = body_service.decode_body(body_content, is_base64)
        if isinstance(decoded, bytes):
            return error_response(
                "Response body is binary",
                suggestions=["Only JSON responses can be converted to models", "Try a different response"],
            )
        body_content = decoded

    # Parse JSON
    try:
        data = json.loads(body_content)
    except json.JSONDecodeError as e:
        return error_response(
            f"Invalid JSON: {e}",
            suggestions=[
                "Response must be valid JSON",
                "Check the response with body() first",
                "Try a different response",
            ],
        )

    # Extract JSON path if specified
    if json_path:
        try:
            # Support simple bracket notation like "Data[0]"
            parts = json_path.replace("[", ".").replace("]", "").split(".")
            for part in parts:
                if part:
                    if part.isdigit():
                        data = data[int(part)]
                    else:
                        data = data[part]
        except (KeyError, IndexError, TypeError) as e:
            return error_response(
                f"JSON path extraction failed: {e}",
                suggestions=[
                    f"Path '{json_path}' not found in response",
                    "Check the response structure with body()",
                    'Try a simpler path like "Data" or "Data[0]"',
                ],
            )

    # Ensure data is dict or list for model generation
    if not isinstance(data, (dict, list)):
        return error_response(
            f"Extracted data is {type(data).__name__}, not dict or list",
            suggestions=[
                "Model generation requires dict or list structure",
                "Adjust json_path to extract a complex object",
            ],
        )

    # Create output directory if needed
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate model using datamodel-codegen Python API
    try:
        generate(
            json.dumps(data),
            input_file_type=InputFileType.Json,
            input_filename="response.json",
            output=output_path,
            output_model_type=DataModelType.PydanticV2BaseModel,
            snake_case_field=True,  # Convert to snake_case
            use_standard_collections=True,  # Use list instead of List
            use_union_operator=True,  # Use | instead of Union
        )
    except Exception as e:
        return error_response(
            f"Model generation failed: {e}",
            suggestions=[
                "Check that the JSON structure is valid",
                "Try simplifying the JSON path",
                "Ensure output directory is writable",
            ],
        )

    # Count fields in generated model
    try:
        model_content = output_path.read_text()
        field_count = model_content.count(": ")  # Count field definitions
    except Exception:
        field_count = "unknown"

    return success_response(
        "Model generated successfully",
        details={"Output": str(output_path), "Fields": field_count, "Size": f"{output_path.stat().st_size} bytes"},
    )
