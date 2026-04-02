"""Tests for conversation persistence — save/load round-trip."""

from __future__ import annotations

import json

import pytest

from ohmycode.core.messages import (
    AssistantMessage,
    SystemMessage,
    ToolResultMessage,
    ToolUseBlock,
    UserMessage,
)
from ohmycode.storage.conversation import (
    _dict_to_msg,
    _msg_to_dict,
    _tool_use_block_from_dict,
    _tool_use_block_to_dict,
    load_conversation,
    save_conversation,
)
import ohmycode.storage.conversation as conv_mod


@pytest.fixture(autouse=True)
def isolate_conversations_dir(tmp_path, monkeypatch):
    """Redirect CONVERSATIONS_DIR to tmp_path so tests don't touch real data."""
    monkeypatch.setattr(conv_mod, "CONVERSATIONS_DIR", tmp_path)
    return tmp_path


# ---- ToolUseBlock serialization ----

def test_tool_use_block_round_trip():
    block = ToolUseBlock(tool_use_id="tu_123", tool_name="bash", params={"command": "ls"})
    d = _tool_use_block_to_dict(block)
    restored = _tool_use_block_from_dict(d)
    assert restored.tool_use_id == "tu_123"
    assert restored.tool_name == "bash"
    assert restored.params == {"command": "ls"}


# ---- Message serialization ----

def test_user_message_round_trip():
    msg = UserMessage(content="hello")
    d = _msg_to_dict(msg)
    restored = _dict_to_msg(d)
    assert isinstance(restored, UserMessage)
    assert restored.content == "hello"


def test_assistant_message_round_trip():
    msg = AssistantMessage(
        content="I'll run that",
        tool_calls=[ToolUseBlock(tool_use_id="t1", tool_name="bash", params={"command": "pwd"})],
    )
    d = _msg_to_dict(msg)
    restored = _dict_to_msg(d)
    assert isinstance(restored, AssistantMessage)
    assert restored.content == "I'll run that"
    assert len(restored.tool_calls) == 1
    assert restored.tool_calls[0].tool_name == "bash"


def test_assistant_message_no_tool_calls():
    msg = AssistantMessage(content="just text", tool_calls=[])
    d = _msg_to_dict(msg)
    assert "tool_calls" not in d or d["tool_calls"] == []
    restored = _dict_to_msg(d)
    assert isinstance(restored, AssistantMessage)
    assert restored.tool_calls == []


def test_tool_result_message_round_trip():
    msg = ToolResultMessage(tool_use_id="t1", content="output text", is_error=False)
    d = _msg_to_dict(msg)
    restored = _dict_to_msg(d)
    assert isinstance(restored, ToolResultMessage)
    assert restored.tool_use_id == "t1"
    assert restored.is_error is False


def test_tool_result_error_flag():
    msg = ToolResultMessage(tool_use_id="t2", content="failed", is_error=True)
    d = _msg_to_dict(msg)
    restored = _dict_to_msg(d)
    assert restored.is_error is True


def test_system_message_round_trip():
    msg = SystemMessage(content="You are helpful.")
    d = _msg_to_dict(msg)
    restored = _dict_to_msg(d)
    assert isinstance(restored, SystemMessage)
    assert restored.content == "You are helpful."


def test_unknown_role_falls_back_to_user():
    d = {"role": "something_weird", "content": "hi"}
    restored = _dict_to_msg(d)
    assert isinstance(restored, UserMessage)


# ---- save_conversation + load_conversation ----

def test_save_and_load_round_trip(isolate_conversations_dir):
    messages = [
        UserMessage(content="hello"),
        AssistantMessage(content="hi there", tool_calls=[]),
        UserMessage(content="run ls"),
        AssistantMessage(
            content="",
            tool_calls=[ToolUseBlock(tool_use_id="t1", tool_name="bash", params={"command": "ls"})],
        ),
        ToolResultMessage(tool_use_id="t1", content="file.py", is_error=False),
    ]
    filename = save_conversation(messages, provider="openai", model="gpt-4o", mode="auto")
    assert filename.endswith(".json")

    result = load_conversation("")
    assert result is not None
    loaded_msgs, metadata = result
    assert len(loaded_msgs) == 5
    assert metadata["provider"] == "openai"
    assert isinstance(loaded_msgs[0], UserMessage)
    assert isinstance(loaded_msgs[3], AssistantMessage)
    assert loaded_msgs[3].tool_calls[0].tool_name == "bash"
    assert isinstance(loaded_msgs[4], ToolResultMessage)


def test_load_by_prefix(isolate_conversations_dir):
    messages = [UserMessage(content="test")]
    filename = save_conversation(messages)
    prefix = filename[:8]  # YYYYMMDD portion
    result = load_conversation(prefix)
    assert result is not None
    _, metadata = result
    assert metadata["filename"] == filename


def test_load_empty_dir(isolate_conversations_dir):
    result = load_conversation("")
    assert result is None


def test_load_no_match(isolate_conversations_dir):
    save_conversation([UserMessage(content="x")])
    result = load_conversation("zzz_no_such_prefix")
    assert result is None


def test_load_corrupt_file(isolate_conversations_dir):
    corrupt = isolate_conversations_dir / "20250101-000000-corrupt1.json"
    corrupt.write_text("this is not json {{{")
    result = load_conversation("20250101")
    assert result is None
