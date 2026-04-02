"""Anthropic Claude provider with streaming and tool calling."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from ohmycode.core.messages import (
    StreamEvent,
    TextChunk,
    TokenUsage,
    ToolCallStart,
    TurnComplete,
    Message,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
)
from ohmycode.providers.base import ToolDef, register_provider


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str = "", base_url: str = "", auth_token: str = "", **kwargs: Any):
        client_kwargs: dict[str, Any] = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url
        if auth_token:
            client_kwargs["auth_token"] = auth_token
        self.client = AsyncAnthropic(**client_kwargs)

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """Convert internal message format to Anthropic API format."""
        result: list[dict] = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            if isinstance(msg, UserMessage):
                result.append({"role": "user", "content": msg.content})

            elif isinstance(msg, AssistantMessage):
                content: list[dict] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.tool_use_id,
                            "name": tc.tool_name,
                            "input": tc.params,
                        }
                    )
                result.append({"role": "assistant", "content": content if content else ""})

            elif isinstance(msg, ToolResultMessage):
                # Anthropic requires tool results in a user message content list.
                # If the previous message is already a user message aggregating tool results, merge.
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_use_id,
                    "content": msg.content,
                }
                if msg.is_error:
                    tool_result_block["is_error"] = True

                if result and result[-1]["role"] == "user" and isinstance(result[-1]["content"], list):
                    result[-1]["content"].append(tool_result_block)
                else:
                    result.append({"role": "user", "content": [tool_result_block]})

            i += 1

        return result

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str,
        model: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        api_messages = self._convert_messages(messages)

        request_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": api_messages,
            "system": system,
        }

        if tools:
            request_kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]

        finish_reason = "stop"
        prompt_tokens = 0
        completion_tokens = 0

        # Accumulate tool-call state
        tool_calls_acc: dict[int, dict] = {}
        current_tool_index: int | None = None

        async with self.client.messages.stream(**request_kwargs) as stream:
            async for event in stream:
                event_type = event.type

                if event_type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        idx = event.index
                        tool_calls_acc[idx] = {
                            "id": block.id,
                            "name": block.name,
                            "arguments": "",
                        }
                        current_tool_index = idx

                elif event_type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield TextChunk(text=delta.text)
                    elif delta.type == "input_json_delta":
                        idx = event.index
                        if idx in tool_calls_acc:
                            tool_calls_acc[idx]["arguments"] += delta.partial_json

                elif event_type == "message_delta":
                    if hasattr(event, "delta"):
                        stop_reason = getattr(event.delta, "stop_reason", None)
                        if stop_reason == "tool_use":
                            finish_reason = "tool_use"
                        elif stop_reason:
                            finish_reason = stop_reason
                    if hasattr(event, "usage"):
                        completion_tokens = getattr(event.usage, "output_tokens", 0)

                elif event_type == "message_start":
                    if hasattr(event, "message") and hasattr(event.message, "usage"):
                        prompt_tokens = getattr(event.message.usage, "input_tokens", 0)
                        completion_tokens = getattr(event.message.usage, "output_tokens", 0)

        # Emit tool-call events
        for idx in sorted(tool_calls_acc.keys()):
            tc = tool_calls_acc[idx]
            try:
                params = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                params = {"_raw": tc["arguments"]}
            yield ToolCallStart(
                tool_name=tc["name"],
                tool_use_id=tc["id"],
                params=params,
            )

        prompt_tokens = prompt_tokens or 0
        completion_tokens = completion_tokens or 0
        yield TurnComplete(
            finish_reason=finish_reason,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def complete(
        self,
        messages: list[Any],
        model: str,
        system_prompt: str = "",
        tools: list[Any] | None = None,
        **kwargs: Any,
    ) -> str:
        api_messages: list[dict] = []
        for msg in messages:
            if hasattr(msg, "to_api_dict"):
                data = msg.to_api_dict()
                api_messages.append({"role": data["role"], "content": data["content"]})
            else:
                api_messages.append(msg)

        request_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": api_messages,
            "system": system_prompt,
        }
        if tools:
            request_kwargs["tools"] = tools
        response = await self.client.messages.create(**request_kwargs)
        parts = getattr(response, "content", []) or []
        return "".join(getattr(part, "text", "") for part in parts if getattr(part, "type", "") == "text")


register_provider("anthropic", AnthropicProvider)
