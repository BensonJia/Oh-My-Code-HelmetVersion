# Gotchas

## 1. Do not `await` `provider.stream()`

`provider.stream()` is an async generator (`async def` + `yield`), not a coroutine.

- Wrong: `async for event in await provider.stream(...)`
- Right: `async for event in provider.stream(...)`

## 2. `rich.Live` conflicts with prompt_toolkit

`rich.Live` uses terminal cursor control for in-place updates and fights `prompt_toolkit`, causing repeated redraws when the terminal scrolls.

- Fix: use `sys.stdout.write` + ANSI escapes (`\r\033[K`) for the spinner

## 3. `permissions.py` must not import `tools/base.py`

That creates a circular import. Permission checks match tool names as strings and do not depend on the `Tool` class.

## 4. tiktoken is inaccurate for Claude models

Expect ~5–15% error. Compression thresholds are conservative (triggers ~10% earlier than the nominal ratio).

## 5. `TOOL_REGISTRY` stores classes, not instances

`register_tool` stores `type[Tool]`; execution does `tool_cls()`. They are not `Tool` instances.

## 6. OpenAI streams tool `arguments` in chunks

Arguments arrive as multiple `delta.tool_calls[idx].function.arguments` fragments. Accumulate by index, then `json.loads` the full string.

## 7. Azure OpenAI needs `AsyncAzureOpenAI`

Do not use plain `AsyncOpenAI` + `base_url`; use `AsyncAzureOpenAI(azure_endpoint=..., api_version=...)`.

## 8. Completion menu background: `bg:default`

Fixed colors (e.g. `bg:#1a1a2e`) look wrong across themes. `bg:default` blends with the terminal background.

## 9. Skill mascot "eyes" use spaces

The mascot's eyes are spaces showing the terminal background, not `on <color>` fills. `on <color>` paints solid blocks and hides the "eyes."

## 10. REPL: raw `console.print` between prompts breaks IME

Rich output between `prompt_toolkit` prompts moves the terminal cursor without updating PT's renderer; macOS Chinese/Japanese IME often stops working after long multi-line output (e.g. `/skills`).

- Fix: wrap prints in `prompt_toolkit.patch_stdout.patch_stdout()` (`_repl_print` in `cli.py`).
# Gotchas

## 1. Do not `await` `provider.stream()`

`provider.stream()` is an async generator (`async def` + `yield`), not a coroutine.

- Wrong: `async for event in await provider.stream(...)`
- Right: `async for event in provider.stream(...)`

## 2. `rich.Live` conflicts with prompt_toolkit

`rich.Live` uses terminal cursor control for in-place updates and fights `prompt_toolkit`, causing repeated redraws when the terminal scrolls.

- Fix: use `sys.stdout.write` + ANSI escapes (`\r\033[K`) for the spinner

## 3. `permissions.py` must not import `tools/base.py`

That creates a circular import. Permission checks match tool names as strings and do not depend on the `Tool` class.

## 4. tiktoken is inaccurate for Claude models

Expect ~5–15% error. Compression thresholds are conservative (triggers ~10% earlier than the nominal ratio).

## 5. `TOOL_REGISTRY` stores classes, not instances

`register_tool` stores `type[Tool]`; execution does `tool_cls()`. They are not `Tool` instances.

## 6. OpenAI streams tool `arguments` in chunks

Arguments arrive as multiple `delta.tool_calls[idx].function.arguments` fragments. Accumulate by index, then `json.loads` the full string.

## 7. Azure OpenAI needs `AsyncAzureOpenAI`

Do not use plain `AsyncOpenAI` + `base_url`; use `AsyncAzureOpenAI(azure_endpoint=..., api_version=...)`.

## 8. Completion menu background: `bg:default`

Fixed colors (e.g. `bg:#1a1a2e`) look wrong across themes. `bg:default` blends with the terminal background.

## 9. Skill mascot “eyes” use spaces

The mascot’s eyes are spaces showing the terminal background, not `on <color>` fills. `on <color>` paints solid blocks and hides the “eyes.”

## 10. REPL: raw `console.print` between prompts breaks IME

Rich output between `prompt_toolkit` prompts moves the terminal cursor without updating PT's renderer; macOS Chinese/Japanese IME often stops working after long multi-line output (e.g. `/skills`).

- Fix: wrap prints in `prompt_toolkit.patch_stdout.patch_stdout()` (`_repl_print` in `cli.py`).
# Gotchas

## 1. Do not `await` `provider.stream()`

`provider.stream()` is an async generator (`async def` + `yield`), not a coroutine.

- Wrong: `async for event in await provider.stream(...)`
- Right: `async for event in provider.stream(...)`

## 2. `rich.Live` conflicts with prompt_toolkit

`rich.Live` uses terminal cursor control for in-place updates and fights `prompt_toolkit`, causing repeated redraws when the terminal scrolls.

- Fix: use `sys.stdout.write` + ANSI escapes (`\r\033[K`) for the spinner

## 3. `permissions.py` must not import `tools/base.py`

That creates a circular import. Permission checks match tool names as strings and do not depend on the `Tool` class.

## 4. tiktoken is inaccurate for Claude models

Expect ~5–15% error. Compression thresholds are conservative (triggers ~10% earlier than the nominal ratio).

## 5. `TOOL_REGISTRY` stores classes, not instances

`register_tool` stores `type[Tool]`; execution does `tool_cls()`. They are not `Tool` instances.

## 6. OpenAI streams tool `arguments` in chunks

Arguments arrive as multiple `delta.tool_calls[idx].function.arguments` fragments. Accumulate by index, then `json.loads` the full string.

## 7. Azure OpenAI needs `AsyncAzureOpenAI`

Do not use plain `AsyncOpenAI` + `base_url`; use `AsyncAzureOpenAI(azure_endpoint=..., api_version=...)`.

## 8. Completion menu background: `bg:default`

Fixed colors (e.g. `bg:#1a1a2e`) look wrong across themes. `bg:default` blends with the terminal background.

## 9. Skill mascot “eyes” use spaces

The mascot’s eyes are spaces showing the terminal background, not `on <color>` fills. `on <color>` paints solid blocks and hides the “eyes.”

## 10. REPL: raw `console.print` between prompts breaks IME

Rich output between `prompt_toolkit` prompts moves the terminal cursor without updating PT's renderer; macOS Chinese/Japanese IME often stops working after long multi-line output (e.g. `/skills`).

- Fix: wrap prints in `prompt_toolkit.patch_stdout.patch_stdout()` (`_repl_print` in `cli.py`).
