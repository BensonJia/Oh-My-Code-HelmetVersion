---
name: debug-ohmycode
description: Guide for debugging OhMyCode issues. Use when user reports errors, unexpected behavior, or connection problems.
---

# Debug OhMyCode

Systematic approach to diagnosing and fixing OhMyCode issues.

## When to Use

- User reports an error or crash
- Tool calls fail unexpectedly
- API connection issues
- Streaming not working
- Context compression misbehaving
- Memory or conversation persistence issues

## Diagnostic Flowchart

```
Error? → Which category?
├── "command not found" → Installation Issue
├── API/connection error → Provider Issue
├── Tool execution error → Tool Issue
├── "context compression failed" → Context Issue
├── Memory/resume not working → Storage Issue
└── Unexpected AI behavior → Prompt Issue
```

## Category 1: Installation Issues

**Symptoms:** `ohmycode: command not found`, `ModuleNotFoundError`

**Steps:**
1. Check installation: `pip3 show ohmycode`
2. Check PATH: `which ohmycode && ohmycode --help`
3. Reinstall: `cd <project_dir> && ./scripts/setup-cli.sh`
4. Check Python version: `python3 --version` (needs 3.9+)

## Category 2: Provider / API Issues

**Symptoms:** `APIError`, `AuthenticationError`, timeout, empty responses

**Steps:**
1. Test API connectivity directly:
```python
from openai import OpenAI
client = OpenAI(api_key="...", base_url="...")
r = client.chat.completions.create(
    model="...", messages=[{"role": "user", "content": "hi"}], max_tokens=10
)
print(r.choices[0].message.content)
```

2. Check config: `cat ~/.ohmycode/config.json`
   - Is `api_key` set?
   - Is `base_url` correct (trailing `/v1`)?
   - Is `model` name correct for this provider?

3. Check provider registration:
```python
from ohmycode.providers.base import PROVIDER_REGISTRY, auto_import_providers
auto_import_providers()
print(list(PROVIDER_REGISTRY.keys()))
```

4. Check for rate limiting: look for 429 errors in output. OpenAI provider retries 3 times with [1, 2, 5]s delays.

5. Azure-specific: verify `azure_endpoint` and `azure_api_version` in config.

## Category 3: Tool Issues

**Symptoms:** Tool returns error, wrong output, tool not found

**Steps:**
1. Check tool is registered:
```python
from ohmycode.tools.base import TOOL_REGISTRY, auto_import_tools
auto_import_tools()
print(list(TOOL_REGISTRY.keys()))
```

2. Test tool directly:
```python
import asyncio
from ohmycode.tools.base import ToolContext
from ohmycode.tools.<name> import <ToolClass>

ctx = ToolContext(mode="auto", agent_depth=0, cwd=".", is_sub_agent=False)
tool = <ToolClass>()
result = asyncio.run(tool.execute({"param": "value"}, ctx))
print(result.output, result.is_error)
```

3. Check permissions: if `mode=default`, dangerous tools need confirmation. Try `--mode auto`.

4. Check `concurrent_safe` flag: if a tool has side effects but is marked `concurrent_safe=True`, it may have race conditions when called in parallel.

## Category 4: Context / Compression Issues

**Symptoms:** "Circuit breaker open", conversations getting cut off, AI forgetting context

**Steps:**
1. Check token budget in config: `token_budget` and `output_tokens_reserved`
2. Check compression thresholds: `ohmycode/core/context.py` → `maybe_compress()`
   - 75% → snip, 80% → micro_compact, 85% → collapse, 90% → auto_compact
3. Circuit breaker trips after 3 compression failures — usually means the LLM API is down
4. For tiktoken accuracy issues: counts are approximate (5-15% off for non-OpenAI models)

**Quick fix:** Increase `token_budget` in config, or start a new conversation.

## Category 5: Storage Issues

**Symptoms:** `--resume` not working, memories not saving, conversations lost

**Steps:**
1. Check directories exist:
```bash
ls -la ~/.ohmycode/conversations/
ls -la ~/.ohmycode/memory/
```

2. Check conversation files: `cat ~/.ohmycode/conversations/<latest>.json | python3 -m json.tool | head`

3. Memory index: `cat ~/.ohmycode/memory/MEMORY.md`

4. Resume matching: `--resume` with no argument loads the most recent file by modification time. With an argument, it matches filename substring.

## Category 6: Prompt / Behavior Issues

**Symptoms:** AI ignores instructions, wrong persona, missing tools in responses

**Steps:**
1. Check what system prompt is built:
```python
from ohmycode.core.system_prompt import build_system_prompt, find_project_instructions
from ohmycode.tools.base import auto_import_tools
auto_import_tools()
prompt = build_system_prompt(mode="auto", cwd=".")
print(prompt)
```

2. Check if `OHMYCODE.md` / `CLAUDE.md` is being found:
```python
from ohmycode.core.system_prompt import find_project_instructions
print(find_project_instructions("."))
```

3. Check memory content: `cat ~/.ohmycode/memory/MEMORY.md`

4. Check `system_prompt_append` in config

## General Debugging Tips

- Add `--mode auto` to skip permission prompts during debugging
- Keep CLI-first workflow: run with `ohmycode` only
- Check `python3 -m pytest tests/ -v` to verify nothing is broken
- Read the error traceback bottom-up: the last frame is usually the cause
- For async issues: look for "RuntimeError: Event loop" — usually means mixing sync/async
