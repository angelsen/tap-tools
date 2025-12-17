"""CDP command execution endpoint."""

import asyncio
from typing import Any, Dict

from fastapi import APIRouter

from webtap.api.models import CDPRequest
import webtap.api.app as app_module

router = APIRouter()


@router.post("/cdp")
async def execute_cdp(request: CDPRequest) -> Dict[str, Any]:
    """Execute arbitrary CDP command.

    Used by MCP js() command for Runtime.evaluate and other CDP operations.
    """
    if not app_module.app_state:
        return {"error": "WebTap not initialized"}
    if not app_module.app_state.cdp.is_connected:
        return {"error": "Not connected to a page"}

    try:
        result = await asyncio.to_thread(app_module.app_state.cdp.execute, request.method, request.params)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}
