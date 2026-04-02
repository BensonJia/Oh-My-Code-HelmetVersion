"""Tests for improved memory extraction (Phase 4)."""

import json

import pytest

from ohmycode.memory.memory import filter_messages_for_extraction, parse_extraction_response


class TestFilterMessages:
    """Only user/assistant text messages should be extracted."""

    def test_keeps_user_messages(self):
        from ohmycode.core.messages import UserMessage
        msgs = [UserMessage(content="hello")]
        filtered = filter_messages_for_extraction(msgs)
        assert len(filtered) == 1

    def test_keeps_assistant_messages(self):
        from ohmycode.core.messages import AssistantMessage
        msgs = [AssistantMessage(content="hi there")]
        filtered = filter_messages_for_extraction(msgs)
        assert len(filtered) == 1

    def test_filters_out_tool_results(self):
        from ohmycode.core.messages import UserMessage, ToolResultMessage
        msgs = [
            UserMessage(content="read file.py"),
            ToolResultMessage(tool_use_id="t1", content="def main(): ...\n" * 100, is_error=False),
        ]
        filtered = filter_messages_for_extraction(msgs)
        assert len(filtered) == 1
        assert filtered[0].content == "read file.py"

    def test_filters_empty_content(self):
        from ohmycode.core.messages import UserMessage, AssistantMessage
        msgs = [
            UserMessage(content="hi"),
            AssistantMessage(content=""),
            UserMessage(content="bye"),
        ]
        filtered = filter_messages_for_extraction(msgs)
        assert len(filtered) == 2


class TestParseExtractionResponse:
    """Robust parsing of LLM extraction output."""

    def test_parse_json_lines(self):
        text = '{"name":"a","type":"user","content":"x"}\n{"name":"b","type":"feedback","content":"y"}'
        result = parse_extraction_response(text)
        assert len(result) == 2
        assert result[0]["name"] == "a"

    def test_parse_json_array(self):
        arr = [
            {"name": "a", "type": "user", "content": "x"},
            {"name": "b", "type": "feedback", "content": "y"},
        ]
        text = json.dumps(arr)
        result = parse_extraction_response(text)
        assert len(result) == 2

    def test_parse_with_markdown_fences(self):
        text = '```json\n{"name":"a","type":"user","content":"x"}\n```'
        result = parse_extraction_response(text)
        assert len(result) == 1

    def test_parse_mixed_garbage(self):
        text = 'Here are the memories:\n{"name":"a","type":"user","content":"x"}\nsome extra text'
        result = parse_extraction_response(text)
        assert len(result) == 1

    def test_parse_empty_returns_empty(self):
        assert parse_extraction_response("") == []
        assert parse_extraction_response("no json here") == []

    def test_rejects_incomplete_objects(self):
        text = '{"name":"a","type":"user"}'  # missing "content"
        result = parse_extraction_response(text)
        assert len(result) == 0
