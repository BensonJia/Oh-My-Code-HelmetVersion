"""Grep tool — search file contents with a regular expression."""

from __future__ import annotations

from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool


@register_tool
class GrepTool(Tool):
    name = "grep"
    description = (
        "Search files for a regex pattern; output as filepath:line:content, max 200 matches."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regular expression pattern",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search (defaults to ctx.cwd)",
            },
            "glob": {
                "type": "string",
                "description": "Glob to limit files searched (e.g. '*.py')",
            },
            "-i": {
                "type": "boolean",
                "description": "Case-insensitive search (default false)",
            },
        },
        "required": ["pattern"],
    }
    concurrent_safe = True

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        pattern_str: str = params["pattern"]
        base = params.get("path") or ctx.cwd
        glob_pat: str = params.get("glob", "**/*")
        case_insensitive: bool = params.get("-i", False)
        result = await ctx.runtime.grep_search(
            pattern_str,
            path=base,
            glob_pat=glob_pat,
            case_insensitive=case_insensitive,
        )
        return ToolResult(
            output=result.output,
            is_error=result.is_error,
            metadata=getattr(result, "metadata", {}),
        )
