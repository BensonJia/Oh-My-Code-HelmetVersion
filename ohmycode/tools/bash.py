"""Bash tool — run commands in a shell."""

from __future__ import annotations

from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool

_DEFAULT_TIMEOUT = 120  # seconds


@register_tool
class BashTool(Tool):
    name = "bash"
    description = "Run a bash command in the shell and return its output."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to run",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds (default 120)",
            },
        },
        "required": ["command"],
    }
    concurrent_safe = False

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        command = params["command"]
        timeout = params.get("timeout", _DEFAULT_TIMEOUT)
        result = await ctx.runtime.exec(command, timeout=timeout)
        return ToolResult(
            output=result.output,
            is_error=result.is_error,
            metadata=getattr(result, "metadata", {}),
        )
