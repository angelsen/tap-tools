"""Generate Pydantic models from HTTP response bodies."""

import json
from datamodel_code_generator import generate, InputFileType, DataModelType
from webtap.app import app
from webtap.commands._builders import check_connection, success_response, error_response
from webtap.commands._code_generation import ensure_output_directory
from webtap.commands._tips import get_mcp_description


mcp_desc = get_mcp_description("to_model")


@app.command(display="markdown", fastmcp={"type": "tool", "description": mcp_desc} if mcp_desc else {"type": "tool"})
def to_model(state, event: int, output: str, model_name: str, json_path: str = None, expr: str = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Generate Pydantic model from request or response body using datamodel-codegen.

    Args:
        event: Event row ID from network() or events()
        output: Output file path for generated model (e.g., "models/customers/group.py")
        model_name: Class name for generated model (e.g., "CustomerGroup")
        json_path: Optional JSON path to extract nested data (e.g., "data[0]")
        expr: Optional Python expression to transform data (has 'body' and 'event' variables)

    Examples:
        to_model(123, "models/user.py", "User", json_path="data[0]")
        to_model(172, "models/form.py", "Form", expr="dict(urllib.parse.parse_qsl(body))")
        to_model(123, "models/clean.py", "Clean", expr="{k: v for k, v in json.loads(body).items() if k != 'meta'}")

    Returns:
        Success message with generation details
    """
    if error := check_connection(state):
        return error

    # Prepare data via service layer
    result = state.service.body.prepare_for_generation(event, json_path, expr)
    if result.get("error"):
        return error_response(result["error"], suggestions=result.get("suggestions", []))

    data = result["data"]

    # Ensure output directory exists
    output_path = ensure_output_directory(output)

    # Generate model using datamodel-codegen Python API
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
                "Try simplifying the JSON path",
                "Ensure output directory is writable",
            ],
        )

    # Count fields in generated model
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
