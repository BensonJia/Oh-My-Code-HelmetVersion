"""Tests for message types and event dataclasses."""

from ohmycode.core.messages import (
    AssistantMessage,
    HelmetReviewResult,
    Message,
    SystemMessage,
    TextChunk,
    TokenUsage,
    ToolCallResult,
    ToolCallStart,
    ToolUseBlock,
    TurnComplete,
    UserMessage,
)


def test_user_message_creation():
    msg = UserMessage(content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"


def test_assistant_message_with_tool_calls():
    tool_use = ToolUseBlock(
        tool_use_id="id_1", tool_name="bash", params={"command": "ls"}
    )
    msg = AssistantMessage(content="Let me check.", tool_calls=[tool_use])
    assert msg.role == "assistant"
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].tool_name == "bash"


def test_system_message():
    msg = SystemMessage(content="You are a helpful assistant.")
    assert msg.role == "system"


def test_text_chunk_event():
    chunk = TextChunk(text="hello")
    assert chunk.text == "hello"


def test_tool_call_start_event():
    event = ToolCallStart(tool_name="bash", tool_use_id="id_1", params={"command": "ls"})
    assert event.tool_name == "bash"


def test_tool_call_result_event():
    event = ToolCallResult(tool_use_id="id_1", result="file.txt", is_error=False)
    assert not event.is_error


def test_turn_complete_event():
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    event = TurnComplete(finish_reason="stop", usage=usage)
    assert event.finish_reason == "stop"
    assert event.usage.total_tokens == 150


def test_helmet_review_result_event():
    event = HelmetReviewResult(
        tool_name="bash",
        severity="high",
        summary="Possible exfiltration attempt.",
        expected_effect="Archive workspace and upload it.",
        recommendation="pause",
    )
    assert event.tool_name == "bash"
    assert event.severity == "high"


def test_message_to_api_format_user():
    msg = UserMessage(content="hello")
    api = msg.to_api_dict()
    assert api == {"role": "user", "content": "hello"}


def test_message_to_api_format_assistant_with_tool_use():
    tool_use = ToolUseBlock(
        tool_use_id="id_1", tool_name="bash", params={"command": "ls"}
    )
    msg = AssistantMessage(content="Let me run that.", tool_calls=[tool_use])
    api = msg.to_api_dict()
    assert api["role"] == "assistant"
    assert len(api["tool_calls"]) == 1
    assert api["tool_calls"][0]["id"] == "id_1"
    assert api["tool_calls"][0]["function"]["name"] == "bash"
