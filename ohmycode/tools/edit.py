"""Edit tool — exact string replacement in a file."""

from __future__ import annotations

from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool


@register_tool
class EditTool(Tool):
    name = "edit"
    description = (
        "Replace an exact substring in a file. old_string must occur exactly once."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path of the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "Substring to replace (must occur exactly once)",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text",
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    }
    concurrent_safe = False

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        file_path = params["file_path"]
        old_string: str = params["old_string"]
        new_string: str = params["new_string"]
        result = await ctx.runtime.edit_file(file_path, old_string, new_string)
        return ToolResult(
            output=result.output,
            is_error=result.is_error,
            metadata=getattr(result, "metadata", {}),
        )
