"""Tool base class, registry, and partitioned concurrent executor."""

from __future__ import annotations

import asyncio
import importlib
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ohmycode.providers.base import ToolDef
from ohmycode.runtime.base import LocalRuntime


@dataclass
class ToolContext:
    """Context passed on each tool invocation."""
    mode: str           # "auto" | "manual" | "semi"
    agent_depth: int    # 0 = top-level agent
    cwd: str            # current working directory
    is_sub_agent: bool
    extra: dict = field(default_factory=dict)
    runtime: Any | None = None
    workspace_root: str = ""
    config: Any | None = None

    def __post_init__(self) -> None:
        if self.runtime is None:
            self.runtime = LocalRuntime(Path(self.cwd))
        if not self.workspace_root:
            self.workspace_root = self.cwd


@dataclass
class ToolResult:
    """Result of a tool execution."""
    output: str
    is_error: bool
    metadata: dict = field(default_factory=dict)


class Tool(ABC):
    """Abstract base class for all tools."""

    name: str = ""
    description: str = ""
    parameters: dict = field(default_factory=dict)
    concurrent_safe: bool = True  # True = safe to run concurrently; False = must run serially

    @abstractmethod
    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        """Run the tool and return a ToolResult."""
        ...

    def to_tool_def(self) -> ToolDef:
        return ToolDef(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


# ── Registry ────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, type[Tool]] = {}


def register_tool(cls: type[Tool]) -> type[Tool]:
    """Register a tool class in the global registry (usable as a decorator)."""
    TOOL_REGISTRY[cls.name] = cls
    return cls


def get_tool_defs() -> list[ToolDef]:
    """Return ToolDef entries for all registered tools."""
    return [cls().to_tool_def() for cls in TOOL_REGISTRY.values()]


# ── Partitioning ─────────────────────────────────────────────────────────────

def partition_tool_calls(
    calls: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split tool calls into concurrent-safe and unsafe groups.

    Each call dict must include ``tool_name``, ``tool_use_id``, and ``params``.
    """
    safe: list[dict] = []
    unsafe: list[dict] = []
    for call in calls:
        tool_cls = TOOL_REGISTRY.get(call["tool_name"])
        if tool_cls is not None and tool_cls.concurrent_safe:
            safe.append(call)
        else:
            unsafe.append(call)
    return safe, unsafe


# ── Executor ────────────────────────────────────────────────────────────────

async def run_tool_calls(
    calls: list[dict],
    ctx: ToolContext,
) -> dict[str, ToolResult]:
    """Run a batch of tool calls; returns a {tool_use_id: ToolResult} map.

    Concurrent-safe tools run via asyncio.gather; unsafe tools run serially.
    """
    safe, unsafe = partition_tool_calls(calls)
    results: dict[str, ToolResult] = {}

    # Run safe tools concurrently
    async def _run_one(call: dict) -> tuple[str, ToolResult]:
        tool_cls = TOOL_REGISTRY.get(call["tool_name"])
        if tool_cls is None:
            return call["tool_use_id"], ToolResult(
                output=f"Unknown tool: {call['tool_name']}", is_error=True
            )
        tool = tool_cls()
        result = await tool.execute(call["params"], ctx)
        return call["tool_use_id"], result

    if safe:
        gathered = await asyncio.gather(*[_run_one(c) for c in safe])
        for tid, res in gathered:
            results[tid] = res

    # Run unsafe tools serially
    for call in unsafe:
        tid, res = await _run_one(call)
        results[tid] = res

    return results


# ── Auto-import ─────────────────────────────────────────────────────────────

def auto_import_tools() -> None:
    """Import all modules under ohmycode/tools/ (triggers @register_tool)."""
    package_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name != "base":
            importlib.import_module(f"ohmycode.tools.{module_info.name}")
