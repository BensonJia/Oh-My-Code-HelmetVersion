"""<TOOL_NAME> 工具 — <brief description>."""

from __future__ import annotations

from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool


@register_tool
class <ToolClass>(Tool):
    name = "<tool_name>"
    description = "<One sentence: what this tool does, when to use it>"
    parameters = {
        "type": "object",
        "properties": {
            # Add your parameters here. Example:
            # "query": {
            #     "type": "string",
            #     "description": "The SQL query to execute",
            # },
        },
        "required": [],  # List required parameter names
    }
    concurrent_safe = True  # True = read-only/safe; False = has side effects

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        # 1. Extract and validate parameters
        # param = params.get("param_name", "default")

        # 2. Execute the tool's logic
        try:
            # Your implementation here
            output = "result"
        except Exception as e:
            return ToolResult(output=f"Error: {e}", is_error=True)

        # 3. Return the result
        return ToolResult(output=output, is_error=False)
