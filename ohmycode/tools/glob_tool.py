"""Glob tool — match file paths by pattern, sorted by modification time."""

from __future__ import annotations

from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool


@register_tool
class GlobTool(Tool):
    name = "glob"
    description = (
        "Search files by glob pattern; results sorted by mtime descending, max 200."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern, e.g. '**/*.py'",
            },
            "path": {
                "type": "string",
                "description": "Root directory to search (defaults to ctx.cwd)",
            },
        },
        "required": ["pattern"],
    }
    concurrent_safe = True

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        pattern: str = params["pattern"]
        base = params.get("path") or ctx.cwd
        result = await ctx.runtime.glob_search(pattern, path=base)
        return ToolResult(
            output=result.output,
            is_error=result.is_error,
            metadata=getattr(result, "metadata", {}),
        )
