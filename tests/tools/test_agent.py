import pytest
from ohmycode.config.config import OhMyCodeConfig
from ohmycode.core.messages import TextChunk, TokenUsage, TurnComplete
from ohmycode.tools.base import ToolContext
from ohmycode.tools.agent import AgentTool, MAX_AGENT_DEPTH


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)


@pytest.mark.asyncio
async def test_agent_depth_limit(ctx):
    """Test that agent respects depth limit."""
    tool = AgentTool()
    # Set depth to max, should fail
    ctx.agent_depth = MAX_AGENT_DEPTH
    result = await tool.execute({"prompt": "test"}, ctx)
    assert result.is_error
    assert "depth limit" in result.output.lower()


@pytest.mark.asyncio
async def test_agent_properties(ctx):
    """Test that AgentTool has correct properties."""
    tool = AgentTool()
    assert tool.name == "agent"
    assert tool.concurrent_safe is False
    assert "prompt" in tool.parameters["properties"]


@pytest.mark.asyncio
async def test_agent_inherits_runtime_and_sandbox(monkeypatch, tmp_path):
    class DummyRuntime:
        pass

    captured = {}

    class FakeLoop:
        def __init__(
            self,
            config,
            confirm_fn=None,
            safety_confirm_fn=None,
            runtime_override=None,
            agent_depth=0,
            cwd_override=None,
            is_sub_agent=False,
            extra_context=None,
        ):
            captured["config"] = config
            captured["runtime_override"] = runtime_override
            captured["agent_depth"] = agent_depth
            captured["cwd_override"] = cwd_override
            captured["is_sub_agent"] = is_sub_agent
            captured["extra_context"] = extra_context

        def initialize(self):
            return None

        def add_user_message(self, prompt):
            captured["prompt"] = prompt

        async def run_turn(self):
            yield TextChunk(text="sub-agent ok")
            yield TurnComplete(finish_reason="stop", usage=TokenUsage(1, 1, 2))

    monkeypatch.setattr("ohmycode.core.loop.ConversationLoop", FakeLoop)

    runtime = DummyRuntime()
    config = OhMyCodeConfig(
        mode="auto",
        sandbox={"enabled": True, "workspace_root": "/workspace", "image": "python:3.11-slim"},
    )
    ctx = ToolContext(
        mode="auto",
        agent_depth=0,
        cwd=str(tmp_path),
        is_sub_agent=False,
        runtime=runtime,
        workspace_root="/workspace",
        config=config,
    )

    result = await AgentTool().execute({"prompt": "inspect project"}, ctx)

    assert not result.is_error
    assert result.output == "sub-agent ok"
    assert captured["runtime_override"] is runtime
    assert captured["config"].sandbox.enabled is True
    assert captured["config"].sandbox.workspace_root == "/workspace"
    assert captured["agent_depth"] == 1
    assert captured["cwd_override"] == str(tmp_path)
    assert captured["is_sub_agent"] is True
    assert captured["prompt"] == "inspect project"
