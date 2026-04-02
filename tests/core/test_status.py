from __future__ import annotations

from ohmycode.config.config import OhMyCodeConfig
from ohmycode.core.loop import ConversationLoop
from ohmycode.core.messages import AssistantMessage, ToolResultMessage, UserMessage


def _make_conv() -> ConversationLoop:
    config = OhMyCodeConfig(
        provider="mock",
        model="test-model",
        mode="auto",
        token_budget=1000,
        output_tokens_reserved=200,
    )
    conv = ConversationLoop(config=config)
    conv._system_prompt = "You are helpful."
    return conv


def test_get_status_snapshot_reports_context_usage():
    conv = _make_conv()
    conv.messages = [
        UserMessage(content="hello"),
        AssistantMessage(content="hi there"),
        ToolResultMessage(tool_use_id="t1", content="tool output"),
    ]

    status = conv.get_status_snapshot()

    assert status["message_count"] == 3
    assert status["token_budget"] == 1000
    assert status["output_reserved"] == 200
    assert status["effective_window"] == 800
    assert status["used_tokens"] > 0
    assert 0 <= status["usage_percent"] <= 100
    assert status["compression_stage"] == "ok"


def test_get_status_snapshot_reports_compression_stage_thresholds():
    conv = _make_conv()

    conv.context_mgr.get_usage_ratio = lambda messages, system_prompt="": 0.77
    status = conv.get_status_snapshot()
    assert status["compression_stage"] == "snip"

    conv.context_mgr.get_usage_ratio = lambda messages, system_prompt="": 0.82
    status = conv.get_status_snapshot()
    assert status["compression_stage"] == "micro_compact"

    conv.context_mgr.get_usage_ratio = lambda messages, system_prompt="": 0.87
    status = conv.get_status_snapshot()
    assert status["compression_stage"] == "collapse"

    conv.context_mgr.get_usage_ratio = lambda messages, system_prompt="": 0.93
    status = conv.get_status_snapshot()
    assert status["compression_stage"] == "auto_compact"
