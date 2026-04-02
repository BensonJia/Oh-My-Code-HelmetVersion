# OhMyCode Architecture

## Overview

OhMyCode is a compact AI coding assistant CLI. Its core execution model is an async agent loop:

1. accept user input
2. stream model output
3. collect tool calls
4. run permission checks
5. run safety review
6. execute approved tools through a workspace runtime
7. feed tool results back to the model

The new security boundary is the runtime layer. High-risk tools no longer touch the host directly; they go through a workspace-scoped runtime, optionally backed by Docker. In REPL mode with sandboxing enabled, the Docker backend now runs as a session-scoped container instead of spawning a fresh container for every tool call.

Runtime LLM selection is config-driven. Main model settings come from `llm` in `config.json`, and the safety reviewer can use a separate `safety.llm_reviewer` service definition. CLI flags no longer override provider credentials or model selection.

## Module Dependency Graph

```text
cli.py -> core/loop.py -> providers/base.py -> providers/openai.py
                       -> providers/anthropic.py
                       -> tools/base.py -> tools/*.py
                       -> core/permissions.py
                       -> core/safety.py
                       -> runtime/base.py -> runtime/docker.py
                       -> core/context.py
                       -> core/system_prompt.py -> memory/memory.py
         skills/loader.py (leaf, invoked from cli.py)
         storage/conversation.py (leaf, invoked from cli.py)
         config/config.py (standalone, read by all modules)
```

Key constraint: `core/permissions.py` must not import `tools/base.py`.

## Data Flow

```text
User input -> cli.py
  -> ConversationLoop.add_user_message()
  -> ConversationLoop.run_turn()
    -> context.maybe_compress()
    -> provider.stream()
      -> yield TextChunk
      -> yield ToolCallStart
    -> permissions.check_permission()
    -> safety.review()
      -> optional yield SafetyAlert
    -> tools.run_tool_calls()
      -> tool.execute(..., ctx.runtime)
      -> yield ToolCallResult
    -> append ToolResultMessage
    -> continue loop until provider stops
  -> yield TurnComplete
-> cli.py render_stream()
```

## Core Modules

| Module | File | Role |
|---|---|---|
| CLI | `cli.py` | REPL, one-shot mode, terminal rendering, confirmation prompts |
| Conversation loop | `core/loop.py` | Main async agent loop, runtime initialization, safety pause flow |
| Messages | `core/messages.py` | Conversation messages and stream events including `SafetyAlert` |
| Permissions | `core/permissions.py` | Rule and mode-based allow/deny/ask decisions |
| Safety | `core/safety.py` | Deterministic pre-execution risk classification plus optional lightweight LLM reviewer |
| Runtime | `runtime/base.py`, `runtime/docker.py` | Workspace-scoped file/process access, Docker sandbox backend |
| Context | `core/context.py` | Token budgeting and compression |
| System prompt | `core/system_prompt.py` | Builds system prompt with project, memory, environment, sandbox info |
| Provider | `providers/base.py` | Provider protocol and registry |
| Tools | `tools/base.py` | Tool registry, context, partitioned execution |
| Memory | `memory/memory.py` | Project/user memory storage and extraction |
| Persistence | `storage/conversation.py` | Conversation save/load |
| Skills | `skills/loader.py` | Skill discovery and loading |
| Config | `config/config.py` | Defaults plus user/project/CLI merge, including sandbox and safety settings |

## Runtime Model

- `LocalRuntime` keeps access inside the current workspace path.
- `DockerSandboxRuntime` bind-mounts the workspace into the container at `/workspace`.
- `SessionDockerRuntime` keeps a named container alive for the whole conversation and executes tools through `docker exec`.
- Resource limits are configured through `sandbox.cpu_limit`, `sandbox.memory_limit`, and `sandbox.pids_limit`.
- `network_enabled=false` maps to Docker `--network none`.
- Tools should treat the runtime as the only valid file/process interface.
- On exit, a session sandbox can be committed and exported to `~/.ohmycode/sandboxes/`. When the same conversation is resumed, the CLI can restore that sandbox before starting the loop.

## Safety Model

- Permissions answer "is this tool allowed in this mode?"
- Safety answers "should this allowed call pause before execution?"
- A paused call emits `SafetyAlert` to the CLI.
- User confirmation can approve once, deny, or auto-approve future calls for that tool in the session.
- The deterministic rule engine runs first.
- If `safety.llm_reviewer.enabled=true`, a small model may escalate contextual risk and improve the explanation.
- The LLM reviewer is advisory only. It can raise severity, but it does not replace permissions or directly execute tools.

## Extension Points

1. New tool: add under `ohmycode/tools/` and register with `@register_tool`
2. New provider: add under `ohmycode/providers/` and register with `register_provider()`
3. New runtime backend: add under `ohmycode/runtime/` and initialize it from `core/loop.py`
4. New safety heuristics: extend `core/safety.py`
5. New skill: add `SKILL.md` under supported skill directories
