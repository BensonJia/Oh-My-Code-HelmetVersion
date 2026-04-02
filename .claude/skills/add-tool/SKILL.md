---
name: add-tool
description: Guide for adding a new tool to OhMyCode. Use when user wants to create a custom tool.
---

# Add a New Tool to OhMyCode

Create a new tool that the AI assistant can use during conversations.

## When to Use

- User says "add a tool", "create a tool", "I want a new tool"
- User describes a capability they want the AI to have (e.g., "I want it to run SQL queries")

## Prerequisites

- Read `docs/DEVELOPMENT_GUIDE.md` for project conventions
- Read `ohmycode/tools/base.py` to understand `Tool`, `ToolContext`, `ToolResult`, `@register_tool`
- Look at an existing tool (e.g., `ohmycode/tools/bash.py`) as reference

## Step-by-Step Guide

### Step 1: Define the Tool

Ask the user:
1. **Tool name** — short, lowercase, snake_case (e.g., `sql_query`, `docker_run`)
2. **Description** — one sentence for the LLM to understand when to use it
3. **Parameters** — what inputs does it need? (JSON Schema format)
4. **Concurrent safety** — can it run in parallel with other tools? (True for read-only, False for side effects)

### Step 2: Create the Tool File

Copy the template from `templates/tool_template.py` to `ohmycode/tools/<tool_name>.py`.

Fill in:
- `name`, `description`, `parameters`, `concurrent_safe` class attributes
- `execute()` method with the actual logic

### Step 3: Write Tests (TDD)

Create `tests/tools/test_<tool_name>.py`:

```python
import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.<tool_name> import <ToolClass>

@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)

@pytest.mark.asyncio
async def test_<tool_name>_basic(ctx):
    tool = <ToolClass>()
    result = await tool.execute({"param": "value"}, ctx)
    assert not result.is_error
    assert "expected" in result.output
```

### Step 4: Verify

```bash
python3 -m pytest tests/tools/test_<tool_name>.py -v   # New tests pass
python3 -m pytest tests/ -v                              # No regressions
```

### Step 5: Test End-to-End

```bash
ohmycode -p "Use the <tool_name> tool to ..." --mode auto
```

### Step 6: Commit

```bash
git add ohmycode/tools/<tool_name>.py tests/tools/test_<tool_name>.py
git commit -m "feat(tools): add <tool_name> tool"
```

## Key Requirements

- Tool file goes in `ohmycode/tools/` — auto-imported, no other files need to change
- Use `@register_tool` decorator on the class
- `execute()` must be `async` and return `ToolResult`
- Never raise exceptions from `execute()` — return `ToolResult(is_error=True)` instead
- Keep the file under 150 lines
- Parameters must be valid JSON Schema

## Common Mistakes

- Forgetting `@register_tool` decorator → tool won't be available
- Raising exceptions instead of returning `ToolResult(is_error=True)` → crashes the loop
- Using `concurrent_safe = True` on tools with side effects → race conditions
- Not handling missing optional parameters → KeyError at runtime
- File name collision with existing tools → check `ohmycode/tools/` first
