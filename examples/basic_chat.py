"""Basic programmatic use of ConversationLoop.

Run:
    python examples/basic_chat.py
"""

from __future__ import annotations

import asyncio
import os

from ohmycode.config.config import OhMyCodeConfig
from ohmycode.core.loop import ConversationLoop
from ohmycode.core.messages import TextChunk, TurnComplete


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

    print("OhMyCode basic chat — type 'quit' to exit\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input or user_input.lower() in ("quit", "exit"):
            break

        conv.add_user_message(user_input)

        print("Assistant: ", end="", flush=True)
        async for event in conv.run_turn():
            if isinstance(event, TextChunk):
                print(event.text, end="", flush=True)
            elif isinstance(event, TurnComplete):
                print(f"\n[finish={event.finish_reason}, tokens={event.usage.total_tokens}]")


if __name__ == "__main__":
    asyncio.run(main())
