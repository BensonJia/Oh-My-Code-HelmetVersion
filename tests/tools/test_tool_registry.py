"""Tests for tool base class, registry, and concurrent partitioning."""
import asyncio
import pytest
from ohmycode.tools.base import (
    TOOL_REGISTRY, Tool, ToolContext, ToolResult,
    get_tool_defs, partition_tool_calls, register_tool, run_tool_calls,
)

class EchoTool(Tool):
    name = "echo"
    description = "Echo the input"
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}}
    concurrent_safe = True
    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(output=params.get("text", ""), is_error=False)

class SlowWriteTool(Tool):
    name = "slow_write"
    description = "Simulate a write operation"
    parameters = {"type": "object", "properties": {"data": {"type": "string"}}}
    concurrent_safe = False
    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(output=f"wrote: {params.get('data', '')}", is_error=False)

def test_register_and_lookup():
    register_tool(EchoTool)
    register_tool(SlowWriteTool)
    assert "echo" in TOOL_REGISTRY
    assert "slow_write" in TOOL_REGISTRY

def test_get_tool_defs():
    register_tool(EchoTool)
    defs = get_tool_defs()
    names = [d.name for d in defs]
    assert "echo" in names

def test_partition_safe_and_unsafe():
    register_tool(EchoTool)
    register_tool(SlowWriteTool)
    calls = [
        {"tool_name": "echo", "tool_use_id": "1", "params": {"text": "a"}},
        {"tool_name": "slow_write", "tool_use_id": "2", "params": {"data": "b"}},
        {"tool_name": "echo", "tool_use_id": "3", "params": {"text": "c"}},
    ]
    safe, unsafe = partition_tool_calls(calls)
    assert len(safe) == 2
    assert len(unsafe) == 1

@pytest.mark.asyncio
async def test_run_tool_calls_concurrent():
    register_tool(EchoTool)
    register_tool(SlowWriteTool)
    calls = [
        {"tool_name": "echo", "tool_use_id": "1", "params": {"text": "hello"}},
        {"tool_name": "slow_write", "tool_use_id": "2", "params": {"data": "world"}},
    ]
    ctx = ToolContext(mode="auto", agent_depth=0, cwd="/tmp", is_sub_agent=False)
    results = await run_tool_calls(calls, ctx)
    assert len(results) == 2
    assert results["1"].output == "hello"
    assert results["2"].output == "wrote: world"
