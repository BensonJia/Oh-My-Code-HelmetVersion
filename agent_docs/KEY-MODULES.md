# Core Module Interfaces

## tools/base.py

```python
@dataclass
class ToolContext:
    mode: str
    agent_depth: int
    cwd: str
    is_sub_agent: bool
    extra: dict
    runtime: Any | None
    workspace_root: str

@dataclass
class ToolResult:
    output: str
    is_error: bool
    metadata: dict

class Tool(ABC):
    name: str
    description: str
    parameters: dict
    concurrent_safe: bool

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult: ...
```

Important rule: tools that execute commands or access files must use `ctx.runtime` instead of direct host APIs.

## runtime/base.py

```python
@dataclass(frozen=True)
class SandboxConfig:
    enabled: bool
    image: str
    workspace_root: str
    cpu_limit: str
    memory_limit: str
    pids_limit: int
    network_enabled: bool

class BaseRuntime:
    async def exec(command, timeout=None) -> RuntimeResult: ...
    async def read_file(file_path, offset=1, limit=None) -> RuntimeResult: ...
    async def write_file(file_path, content) -> RuntimeResult: ...
    async def edit_file(file_path, old_string, new_string) -> RuntimeResult: ...
    async def glob_search(pattern, path=None) -> RuntimeResult: ...
    async def grep_search(pattern, path=None, glob_pat="**/*", case_insensitive=False) -> RuntimeResult: ...
```

`LocalRuntime` enforces workspace-only access on the host. `DockerSandboxRuntime` maps the same contract into a container rooted at `/workspace`.

## providers/base.py

```python
class Provider(Protocol):
    name: str
    async def stream(messages, tools, system, model, **kwargs) -> AsyncIterator[StreamEvent]: ...
```

`Provider.stream()` must yield events in order:

1. `TextChunk`
2. `ToolCallStart`
3. `TurnComplete`

## core/loop.py

`ConversationLoop` owns:

- provider initialization
- runtime selection
- system prompt assembly
- message history
- permission checks
- safety review
- tool execution
- event emission to CLI

New behavior: after permissions but before tool execution, the loop calls `SafetyEngine.review(...)`. If the review says a call should pause, the loop yields `SafetyAlert` and waits on `safety_confirm_fn`.

## core/messages.py

Conversation messages:

- `UserMessage`
- `AssistantMessage`
- `ToolResultMessage`
- `SystemMessage`

Stream events:

- `TextChunk`
- `ToolCallStart`
- `ToolCallResult`
- `SafetyAlert`
- `TurnComplete`
- `TokenUsage`

All conversation messages implement `to_api_dict()`.

## core/permissions.py

```python
check_permission(tool_name, params, mode, rules, auto_approved) -> PermissionResult
```

This layer decides `allow`, `deny`, or `ask` from static rules and session mode. It does not inspect tool classes and must remain decoupled from `tools/base.py`.

## core/safety.py

```python
SafetyEngine.review(tool_name, params, recent_messages) -> SafetyReview
```

This module has two layers:

- `review_sync(...)`: deterministic rules for obvious dangerous commands and sensitive paths
- `review(...)`: optional async LLM-assisted review that can escalate contextual risk when enabled

The LLM reviewer must be treated as advisory. It supplements severity classification and explanation, but rule-based permissions and user confirmation remain authoritative.

`core/safety.py` now exposes explicit helper boundaries for the reviewer:

- `build_llm_reviewer_system_prompt()`
- `build_llm_reviewer_payload(...)`
- `parse_llm_reviewer_response(raw)`

Keep these aligned. If you change the prompt contract, update the parser and tests in the same change.

## config/config.py

```python
load_config(cli_overrides) -> OhMyCodeConfig
merge_configs(base, override) -> dict
```

`OhMyCodeConfig` now includes nested settings:

- `sandbox`: Docker image, workspace root, CPU/memory/PID limits, network mode
- `safety`: enable flag, pause threshold, dangerous command patterns, sensitive path markers
