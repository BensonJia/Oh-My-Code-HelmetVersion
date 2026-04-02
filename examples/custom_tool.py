"""Example: adding a custom tool with @register_tool.

This example registers a "word_count" tool and runs a single-turn conversation
that invokes it.

Run:
    python examples/custom_tool.py
"""

from __future__ import annotations

import asyncio
import os

from ohmycode.config.config import OhMyCodeConfig
from ohmycode.core.loop import ConversationLoop
from ohmycode.core.messages import TextChunk, ToolCallResult, TurnComplete
from ohmycode.tools.base import ToolContext, ToolResult, register_tool


# ── Register a custom tool ────────────────────────────────────────────────────

@register_tool(
    name="word_count",
    description="Count the number of words in a given text.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to count words in.",
            }
        },
        "required": ["text"],
    },
)
async def word_count(text: str, ctx: ToolContext) -> ToolResult:
    count = len(text.split())
    return ToolResult(output=f"{count} words")


# ── Run a conversation that uses the tool ─────────────────────────────────────

async def main() -> None:
    config = OhMyCodeConfig(
        provider="openai",
        model="gpt-4o-mini",
        mode="auto",
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=os.environ.get("OPENAI_BASE_URL", ""),
    )

    conv = ConversationLoop(config=config)
    conv.initialize()

    conv.add_user_message(
        "Use the word_count tool to count the words in: "
        "'The quick brown fox jumps over the lazy dog'"
    )

    async for event in conv.run_turn():
        if isinstance(event, TextChunk):
            print(event.text, end="", flush=True)
        elif isinstance(event, ToolCallResult):
            print(f"\n[tool result: {event.result}]")
        elif isinstance(event, TurnComplete):
            print(f"\n[done — finish={event.finish_reason}]")


if __name__ == "__main__":
    asyncio.run(main())
