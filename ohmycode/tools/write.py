"""Write tool — create or overwrite file contents."""

from __future__ import annotations

from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool


@register_tool
class WriteTool(Tool):
    name = "write"
    description = "Create a new file or overwrite an existing one."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path of the file",
            },
            "content": {
                "type": "string",
                "description": "Content to write",
            },
        },
        "required": ["file_path", "content"],
    }
    concurrent_safe = False

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        file_path = params["file_path"]
        content = params["content"]
        result = await ctx.runtime.write_file(file_path, content)
        return ToolResult(
            output=result.output,
            is_error=result.is_error,
            metadata=getattr(result, "metadata", {}),
        )
