"""Tests for the Anthropic provider — registration and message conversion."""

import pytest

from ohmycode.core.messages import (
    AssistantMessage,
    ToolResultMessage,
    ToolUseBlock,
    UserMessage,
)
from ohmycode.providers.base import PROVIDER_REGISTRY


def test_anthropic_provider_is_registered():
    import ohmycode.providers.anthropic  # noqa: F401
    assert "anthropic" in PROVIDER_REGISTRY


def test_anthropic_provider_instantiation():
    from ohmycode.providers.anthropic import AnthropicProvider
    provider = AnthropicProvider(api_key="test-key")
    assert provider.name == "anthropic"


# ---- _convert_messages ----

@pytest.fixture
def provider():
    from ohmycode.providers.anthropic import AnthropicProvider
    return AnthropicProvider(api_key="test-key")


def test_convert_user_message(provider):
    msgs = [UserMessage(content="hello")]
    result = provider._convert_messages(msgs)
    assert result == [{"role": "user", "content": "hello"}]


def test_convert_assistant_text_only(provider):
    msgs = [AssistantMessage(content="I will help", tool_calls=[])]
    result = provider._convert_messages(msgs)
    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] == [{"type": "text", "text": "I will help"}]


def test_convert_assistant_with_tool_call(provider):
    msgs = [
        AssistantMessage(
            content="Let me run that",
            tool_calls=[ToolUseBlock(tool_use_id="t1", tool_name="bash", params={"command": "ls"})],
        )
    ]
    result = provider._convert_messages(msgs)
    content = result[0]["content"]
    assert len(content) == 2
    assert content[0] == {"type": "text", "text": "Let me run that"}
    assert content[1]["type"] == "tool_use"
    assert content[1]["name"] == "bash"
    assert content[1]["input"] == {"command": "ls"}


def test_convert_assistant_empty_content(provider):
    """Assistant with tool calls but no text content."""
    msgs = [
        AssistantMessage(
            content="",
            tool_calls=[ToolUseBlock(tool_use_id="t1", tool_name="read", params={"file_path": "/x"})],
        )
    ]
    result = provider._convert_messages(msgs)
    content = result[0]["content"]
    # No text block because content is empty
    assert len(content) == 1
    assert content[0]["type"] == "tool_use"


def test_convert_tool_result_creates_user_message(provider):
    """A standalone ToolResultMessage becomes a user message with content list."""
    msgs = [ToolResultMessage(tool_use_id="t1", content="output", is_error=False)]
    result = provider._convert_messages(msgs)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert isinstance(result[0]["content"], list)
    block = result[0]["content"][0]
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "t1"
    assert "is_error" not in block  # not set when False


def test_convert_tool_result_error_flag(provider):
    msgs = [ToolResultMessage(tool_use_id="t1", content="fail", is_error=True)]
    result = provider._convert_messages(msgs)
    block = result[0]["content"][0]
    assert block["is_error"] is True


def test_convert_consecutive_tool_results_merge(provider):
    """Multiple consecutive ToolResultMessages should merge into one user message."""
    msgs = [
        ToolResultMessage(tool_use_id="t1", content="out1", is_error=False),
        ToolResultMessage(tool_use_id="t2", content="out2", is_error=False),
        ToolResultMessage(tool_use_id="t3", content="out3", is_error=True),
    ]
    result = provider._convert_messages(msgs)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert len(result[0]["content"]) == 3
    assert result[0]["content"][2]["is_error"] is True


def test_convert_full_conversation(provider):
    """Full exchange: user → assistant(tool) → tool_result → assistant."""
    msgs = [
        UserMessage(content="list files"),
        AssistantMessage(
            content="",
            tool_calls=[ToolUseBlock(tool_use_id="t1", tool_name="bash", params={"command": "ls"})],
        ),
        ToolResultMessage(tool_use_id="t1", content="a.py\nb.py", is_error=False),
        AssistantMessage(content="I found 2 files.", tool_calls=[]),
    ]
    result = provider._convert_messages(msgs)
    assert len(result) == 4
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"
    assert result[2]["role"] == "user"  # tool result wrapped in user
    assert result[3]["role"] == "assistant"


def test_convert_tool_result_after_user_message_no_merge(provider):
    """ToolResultMessage after a regular UserMessage should NOT merge (different content type)."""
    msgs = [
        UserMessage(content="hello"),
        ToolResultMessage(tool_use_id="t1", content="out", is_error=False),
    ]
    result = provider._convert_messages(msgs)
    assert len(result) == 2
    assert result[0]["content"] == "hello"  # string, not list
    assert isinstance(result[1]["content"], list)  # tool result is list
