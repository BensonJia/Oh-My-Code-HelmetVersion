---
name: add-provider
description: Guide for adding a new LLM provider to OhMyCode. Use when user wants to connect a new AI model backend.
---

# Add a New LLM Provider to OhMyCode

Connect a new LLM backend (e.g., Gemini, Ollama, DeepSeek, local models).

## When to Use

- User says "add a provider", "connect to Gemini", "support Ollama"
- User wants to use a model from a new API that isn't OpenAI-compatible

## Prerequisites

- Read `docs/DEVELOPMENT_GUIDE.md`
- Read `ohmycode/providers/base.py` to understand `Provider` Protocol, `register_provider()`
- Read `ohmycode/core/messages.py` for `TextChunk`, `ToolCallStart`, `TurnComplete`, `TokenUsage`
- Look at `ohmycode/providers/openai.py` as reference

## Step-by-Step Guide

### Step 1: Understand the Provider Protocol

Every provider must implement one method:

```python
async def stream(
    self,
    messages: list[Message],
    tools: list[ToolDef],
    system: str,
    model: str,
    **kwargs,
) -> AsyncIterator[StreamEvent]:
```

It must yield these events in order:
1. `TextChunk(text="...")` — for each streamed text token
2. `ToolCallStart(tool_name="...", tool_use_id="...", params={...})` — for each tool call
3. `TurnComplete(finish_reason="stop"|"tool_use", usage=TokenUsage(...))` — always last

### Step 2: Create the Provider File

Copy `templates/provider_template.py` to `ohmycode/providers/<name>.py`.

Fill in:
- `__init__()` — initialize the API client
- `stream()` — handle the streaming response format of the target API

### Step 3: Handle Message Conversion

Different APIs have different message formats. Key conversions:
- `UserMessage` → the API's user message format
- `AssistantMessage` (with `tool_calls`) → the API's assistant + tool use format
- `ToolResultMessage` → the API's tool result format
- `system` parameter → some APIs put it in messages, some as a separate param

### Step 4: Write Tests

Create `tests/providers/test_<name>_provider.py`:

```python
import pytest
from ohmycode.providers.base import PROVIDER_REGISTRY

def test_provider_is_registered():
    import ohmycode.providers.<name>
    assert "<name>" in PROVIDER_REGISTRY

def test_provider_instantiation():
    from ohmycode.providers.<name> import <ProviderClass>
    provider = <ProviderClass>(api_key="test")
    assert provider.name == "<name>"
```

### Step 5: Add Config Support

Add any new config fields to `ohmycode/config/config.py` `OhMyCodeConfig` class and `DEFAULT_CONFIG` dict if needed (e.g., `gemini_api_key`).

### Step 6: Verify

```bash
python3 -m pytest tests/ -v                              # No regressions
ohmycode -p "Hello" --provider <name> --model <model>      # End-to-end test
```

### Step 7: Commit

```bash
git commit -m "feat(providers): add <name> provider"
```

## Key Requirements

- File goes in `ohmycode/providers/` — auto-imported via `auto_import_providers()`
- Call `register_provider("<name>", <Class>)` at module level
- `stream()` must be an async generator (use `yield`)
- Always yield `TurnComplete` as the last event
- Handle `tools=[]` case (no tool use)
- Never raise from `stream()` during normal API errors — the loop handles retries

## Common Mistakes

- Forgetting to call `register_provider()` → provider not found at runtime
- Not yielding `TurnComplete` → loop hangs waiting for turn end
- `finish_reason` wrong: use `"tool_use"` when model wants to call tools, `"stop"` when done
- Not handling streaming tool call deltas (arguments come in chunks)
- Not converting message formats correctly → API returns 400 errors
