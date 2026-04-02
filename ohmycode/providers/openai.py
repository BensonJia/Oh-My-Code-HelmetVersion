"""OpenAI-compatible provider (OpenAI, Azure OpenAI, Ollama, etc.)."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI, AsyncAzureOpenAI
from openai import RateLimitError, APIStatusError

from ohmycode.core.messages import (
    StreamEvent,
    TextChunk,
    TokenUsage,
    ToolCallStart,
    TurnComplete,
    Message,
)
from ohmycode.providers.base import Provider, ToolDef, register_provider


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        azure_endpoint: str = "",
        azure_api_version: str = "2024-02-01",
        **kwargs: Any,
    ):
        if azure_endpoint:
            self.client = AsyncAzureOpenAI(
                api_key=api_key,
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint,
            )
        else:
            client_kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            self.client = AsyncOpenAI(**client_kwargs)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str,
        model: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        api_messages = [{"role": "system", "content": system}]
        for msg in messages:
            api_messages.append(msg.to_api_dict())

        api_tools = [t.to_api_dict() for t in tools] if tools else None

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "stream": True,
        }
        if api_tools:
            request_kwargs["tools"] = api_tools

        MAX_RETRIES = 3
        RETRY_DELAYS = [1, 2, 5]

        response = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(**request_kwargs)
                break
            except RateLimitError:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                else:
                    raise
            except APIStatusError as e:
                if e.status_code == 503 and attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                else:
                    raise

        tool_calls_acc: dict[int, dict] = {}
        finish_reason = "stop"
        prompt_tokens = 0
        completion_tokens = 0

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            if chunk.choices[0].finish_reason:
                fr = chunk.choices[0].finish_reason
                finish_reason = "tool_use" if fr == "tool_calls" else fr

            if delta.content:
                yield TextChunk(text=delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc_delta.id or "",
                            "name": tc_delta.function.name or "" if tc_delta.function else "",
                            "arguments": "",
                        }
                    if tc_delta.id:
                        tool_calls_acc[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0

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
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if hasattr(msg, "to_api_dict"):
                api_messages.append(msg.to_api_dict())
            else:
                api_messages.append(msg)

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "stream": False,
        }
        if tools:
            request_kwargs["tools"] = [t.to_api_dict() if hasattr(t, "to_api_dict") else t for t in tools]
        response = await self.client.chat.completions.create(**request_kwargs)
        message = response.choices[0].message if response.choices else None
        return getattr(message, "content", "") or ""


register_provider("openai", OpenAIProvider)
