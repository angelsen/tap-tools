"""Generate Pydantic models from HTTP request/response bodies."""

import json
from datamodel_code_generator import generate, InputFileType, DataModelType
from webtap.app import app
from webtap.commands._builders import success_response, error_response
from webtap.commands._code_generation import ensure_output_directory, prepare_generation_data
from webtap.commands._tips import get_mcp_description


mcp_desc = get_mcp_description("to_model")


@app.command(display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": mcp_desc or ""})
def to_model(
    state,
    id: int,
    output: str,
    model_name: str,
    target: str,
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
    data, _, error = prepare_generation_data(state, id, target, field, json_path, expr)
    if error:
        return error

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
