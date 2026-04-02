"""Tests for ContextManager (Task 16) — TDD first."""

import pytest
from ohmycode.core.context import ContextManager
from ohmycode.core.messages import AssistantMessage, UserMessage


def test_token_count_basic():
    mgr = ContextManager(token_budget=1000, output_reserved=200)
    messages = [UserMessage(content="Hello world"), AssistantMessage(content="Hi there")]
    count = mgr.count_tokens(messages, system_prompt="You are helpful.")
    assert count > 0
    assert count < 100


def test_usage_ratio():
    mgr = ContextManager(token_budget=1000, output_reserved=200)
    messages = [UserMessage(content="x " * 400)]
    ratio = mgr.get_usage_ratio(messages, "system")
    assert 0.0 < ratio < 1.0


def test_snip_preserves_recent():
    mgr = ContextManager(token_budget=100, output_reserved=20)
    messages = [
        UserMessage(content="old 1"), AssistantMessage(content="old reply 1"),
        UserMessage(content="old 2"), AssistantMessage(content="old reply 2"),
        UserMessage(content="recent"), AssistantMessage(content="recent reply"),
    ]
    compressed = mgr.snip(messages)
    assert compressed[-1].content == "recent reply"
    assert len(compressed) < len(messages)


def test_count_tokens_empty():
    mgr = ContextManager(token_budget=1000, output_reserved=200)
    count = mgr.count_tokens([], system_prompt="")
    assert count == 0


def test_count_tokens_no_system():
    mgr = ContextManager(token_budget=1000, output_reserved=200)
    messages = [UserMessage(content="Hello")]
    count = mgr.count_tokens(messages, system_prompt="")
    assert count > 0


def test_usage_ratio_large_input():
    mgr = ContextManager(token_budget=100, output_reserved=10)
    # Effective window = 100 - 10 = 90
    # "x " * 400 = ~800 tokens which exceeds window => ratio > 1.0 possible
    messages = [UserMessage(content="x " * 400)]
    ratio = mgr.get_usage_ratio(messages, "")
    assert ratio > 0.0


def test_snip_removes_at_least_two():
    mgr = ContextManager(token_budget=1000, output_reserved=200)
    messages = [
        UserMessage(content="msg1"),
        AssistantMessage(content="reply1"),
        UserMessage(content="msg2"),
        AssistantMessage(content="reply2"),
    ]
    compressed = mgr.snip(messages)
    assert len(compressed) <= len(messages) - 2


def test_snip_minimal_messages():
    """Snip on very few messages should still work."""
    mgr = ContextManager(token_budget=1000, output_reserved=200)
    messages = [UserMessage(content="hi"), AssistantMessage(content="hello")]
    compressed = mgr.snip(messages)
    # Should return something (at least empty list or reduced list)
    assert isinstance(compressed, list)


def test_circuit_breaker_raises_after_failures():
    """Circuit breaker should raise RuntimeError after 3 failures."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    mgr = ContextManager(token_budget=1000, output_reserved=200)
    messages = [UserMessage(content="hello")]

    # Simulate a broken provider
    broken_provider = MagicMock()
    broken_provider.complete = AsyncMock(side_effect=Exception("API error"))

    async def run():
        for _ in range(3):
            try:
                await mgr.micro_compact(messages, broken_provider, "model")
            except Exception:
                pass
        # 4th call should raise RuntimeError (circuit breaker open)
        with pytest.raises(RuntimeError, match="Circuit breaker"):
            await mgr.micro_compact(messages, broken_provider, "model")

    asyncio.run(run())
