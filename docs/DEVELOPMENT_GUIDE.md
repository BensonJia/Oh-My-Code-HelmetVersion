# OhMyCode Development Guide

This is the implementation reference for OhMyCode contributors and agents.

## Project Layout

```text
ohmycode/
├── __main__.py          # CLI entry
├── cli.py               # REPL + one-shot mode, streaming render
├── core/
│   ├── messages.py      # Message + event dataclasses
│   ├── loop.py          # Main conversation loop
│   ├── context.py       # Context compression
│   ├── permissions.py   # Rule + mode permission pipeline
│   ├── safety.py        # Pre-execution safety review
│   └── system_prompt.py # System prompt assembly
├── providers/
│   ├── base.py
│   ├── openai.py
│   └── anthropic.py
├── runtime/
│   ├── base.py          # Runtime abstraction + LocalRuntime
│   └── docker.py        # Docker sandbox runtime
├── tools/
│   ├── base.py
│   ├── bash.py
│   ├── read.py
│   ├── edit.py
│   ├── write.py
│   ├── glob_tool.py
│   ├── grep.py
│   ├── web_fetch.py
│   ├── web_search.py
│   └── agent.py
├── memory/
├── storage/
└── config/
    └── config.py
```

## Dependency Shape

```text
cli.py -> core/loop.py -> providers/base.py
                       -> tools/base.py -> core/permissions.py
                       -> core/safety.py
                       -> runtime/base.py -> runtime/docker.py
                       -> core/context.py
                       -> core/system_prompt.py -> memory/memory.py
config/config.py is standalone
storage/conversation.py is standalone
```

Constraint: `core/permissions.py` must not import `tools/base.py`.

## Security Model

There are now two independent checks before risky execution:

1. Permission rules
2. Safety review

Permission checks decide whether a call is allowed in principle. Safety review decides whether an allowed call should pause for explicit approval.

High-risk tools must execute through `ctx.runtime`. Do not call host shell or host filesystem APIs directly from these tools.

When enabled, the safety layer may also call a lightweight reviewer model. That reviewer is not an authorization layer by itself. It is only allowed to escalate risk or improve the explanation for suspicious multi-step behavior.

## Runtime Rules

- `LocalRuntime` is workspace-scoped and rejects paths outside the workspace.
- `DockerSandboxRuntime` bind-mounts the workspace into the container at `/workspace`.
- `SessionDockerRuntime` keeps one Docker container alive for the whole REPL session when sandboxing is enabled.
- Use `sandbox.network_enabled=false` to run with `docker run --network none`.
- CPU, memory, and PID limits come from config.
- On REPL exit, the operator can export the current sandbox to `~/.ohmycode/sandboxes/` and restore it later when resuming the same conversation.

## Configuration

Config merges in this order:

```text
defaults < ~/.ohmycode/config.json < CLI session overrides
```

LLM service settings are config-only. The CLI no longer accepts `--provider`, `--model`, `--api-key`, or `--base-url`.

Important nested config:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "base_url": "",
    "api_key": ""
  },
  "sandbox": {
    "enabled": false,
    "image": "python:3.11-slim",
    "workspace_root": "/workspace",
    "cpu_limit": "1.0",
    "memory_limit": "512m",
    "pids_limit": 256,
    "network_enabled": false
  },
  "safety": {
    "enabled": true,
    "pause_on_severity": "medium",
    "llm_reviewer": {
      "enabled": false,
      "model": "gpt-4o-mini"
    }
  }
}
```

## Adding A Tool

Create a file under `ohmycode/tools/`, subclass `Tool`, and register it.

```python
from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool

@register_tool
class MyTool(Tool):
    name = "my_tool"
    description = "Description for the LLM"
    parameters = {"type": "object", "properties": {}, "required": []}
    concurrent_safe = True

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        result = await ctx.runtime.exec("echo hello")
        return ToolResult(output=result.output, is_error=result.is_error)
```

## Adding A Provider

Create a file under `ohmycode/providers/` implementing:

```python
class MyProvider:
    name = "my_provider"

    async def stream(self, messages, tools, system, model, **kwargs):
        ...
```

Register it with `register_provider("my_provider", MyProvider)`.

## Code Style

- file size under 500 lines
- function size under 50 lines
- public functions typed
- stdlib imports first, third-party second, project imports last
- async-first for I/O
- return errors as values from tools/runtime instead of raising

## Testing

- mirror the source layout under `tests/`
- use `pytest` and `pytest-asyncio`
- mark async tests with `@pytest.mark.asyncio`
- run focused tests first, then full suite

Commands:

```bash
python -m pytest tests/runtime/test_docker.py -v
python -m pytest tests/core/test_safety.py tests/core/test_loop.py -v
python -m pytest tests/ -v
```

## Workflow For New Features

1. read architecture and module docs
2. decide module ownership before coding
3. write failing tests first
4. implement minimal code to pass
5. run full test suite
6. update docs if core behavior changed

## CLI Policy

Always run this repository through `ohmycode` when doing manual end-to-end checks.

## Setup On Windows

Use PowerShell from the repository root:

```powershell
./scripts/setup-cli.ps1
ohmycode --help
ohmycode
```

The PowerShell setup script installs the package in editable mode, creates stable shims in `%USERPROFILE%\.local\bin`, and appends the Python scripts directory plus that local bin directory to the user PATH.
