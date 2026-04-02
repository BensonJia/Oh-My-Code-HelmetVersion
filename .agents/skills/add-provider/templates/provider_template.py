"""<PROVIDER_NAME> Provider — connect to <Service Name> API."""

from __future__ import annotations

from typing import Any, AsyncIterator

from ohmycode.core.messages import (
    Message,
    StreamEvent,
    TextChunk,
    TokenUsage,
    ToolCallStart,
    TurnComplete,
)
from ohmycode.providers.base import ToolDef, register_provider


class <ProviderClass>:
    """Provider for <Service Name> API."""

    name = "<provider_name>"

    def __init__(self, api_key: str = "", **kwargs: Any):
        # Initialize your API client here
        # self.client = SomeAsyncClient(api_key=api_key)
        pass

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str,
        model: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        # 1. Convert messages to the API's format
        api_messages = []
        for msg in messages:
            api_messages.append(msg.to_api_dict())

        # 2. Convert tools to the API's format
        api_tools = [t.to_api_dict() for t in tools] if tools else None

        # 3. Make the streaming API call
        # response = await self.client.chat(messages=api_messages, ...)

        # 4. Yield events as they arrive
        # async for chunk in response:
        #     if chunk.has_text:
        #         yield TextChunk(text=chunk.text)
        #     if chunk.has_tool_call:
        #         yield ToolCallStart(
        #             tool_name=chunk.tool_name,
        #             tool_use_id=chunk.tool_id,
        #             params=chunk.tool_params,
        #         )

        # 5. Always yield TurnComplete as the last event
        yield TurnComplete(
            finish_reason="stop",  # or "tool_use" if tools were called
            usage=TokenUsage(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            ),
        )


register_provider("<provider_name>", <ProviderClass>)
