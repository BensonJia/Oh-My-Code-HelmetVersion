"""Example: implementing and registering a mock/custom provider.

This shows how to create a provider that does not call any external API —
useful for testing or local prototyping.

Run:
    python examples/custom_provider.py
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from ohmycode.config.config import OhMyCodeConfig
from ohmycode.core.loop import ConversationLoop
from ohmycode.core.messages import (
    Message,
    TextChunk,
    TokenUsage,
    TurnComplete,
    StreamEvent,
)
from ohmycode.providers.base import ToolDef, register_provider


# ── Implement a custom provider ───────────────────────────────────────────────

class EchoProvider:
    """A trivial provider that echoes the last user message back."""

    name = "echo"

    def __init__(self, **kwargs: Any):
        pass

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str,
        model: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        # Find the last user message
        last_user = ""
        for msg in reversed(messages):
            if hasattr(msg, "role") and msg.role == "user":
                last_user = msg.content  # type: ignore[attr-defined]
                break

        response = f"Echo: {last_user}"
        # Simulate token-by-token streaming
        for word in response.split():
            yield TextChunk(text=word + " ")

        yield TurnComplete(
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=len(last_user.split()),
                completion_tokens=len(response.split()),
                total_tokens=len(last_user.split()) + len(response.split()),
            ),
        )


# Register the provider under the name "echo"
register_provider("echo", EchoProvider)


# ── Use the custom provider ───────────────────────────────────────────────────

async def main() -> None:
    config = OhMyCodeConfig(
        provider="echo",
        model="echo-1",
        mode="auto",
        api_key="",
    )

    conv = ConversationLoop(config=config)
    # Skip initialize() to avoid auto_import_providers overriding our registration
    conv._provider = EchoProvider()
    conv._system_prompt = "You are a helpful assistant."

    conv.add_user_message("Hello, world!")

    print("Response: ", end="", flush=True)
    async for event in conv.run_turn():
        if isinstance(event, TextChunk):
            print(event.text, end="", flush=True)
        elif isinstance(event, TurnComplete):
            print(f"\n[done — tokens={event.usage.total_tokens}]")


if __name__ == "__main__":
    asyncio.run(main())
