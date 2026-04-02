---
name: gen-tests
description: Generate high-quality tests for OhMyCode modules. Use when user wants to create, add, or generate tests for a module or file.
---

# Generate Tests for OhMyCode

Generate project-convention-compliant tests for a given module or file.

This skill is part of the **OhMyCode development closed-loop**:

```
编码 ──→ /gen-tests ──→ /run-tests ──→ 分析失败 ──→ 修代码 ──╮
 ↑                                                            │
 ╰────────────────────────────────────────────────────────────╯
```

After generating tests, **always proceed to `/run-tests`** to verify them.

## When to Use

- User says "gen tests", "write tests", "add tests for …"
- User provides a module name or file path (e.g., `ohmycode/tools/bash.py`, `core/loop`)
- As part of the development loop: just finished writing/modifying source code and need tests

## Input

`$ARGUMENTS` — module name or file path to test (e.g., `ohmycode/tools/bash.py`, `core/loop`, `providers/anthropic`).

If `$ARGUMENTS` is empty, ask the user which module to generate tests for.

## Step 1 — Resolve Target

Map the argument to a source file path:

| Argument form | Resolved source path |
|---|---|
| `ohmycode/tools/bash.py` | use as-is |
| `tools/bash` | `ohmycode/tools/bash.py` |
| `core/loop` | `ohmycode/core/loop.py` |
| `providers/openai` | `ohmycode/providers/openai.py` |
| `config` | `ohmycode/config/config.py` |

Read the resolved source file. Identify:
- Public classes / functions (skip `_private` unless critical)
- Async vs sync interfaces
- External dependencies (API calls, file I/O, subprocesses)
- Branch paths (if/else, error returns, edge cases)

## Step 2 — Read Existing Test Patterns

1. **Read `tests/conftest.py`** to learn available fixtures:
   - `MockProvider` — fake LLM that yields configurable responses, use for anything touching providers
   - `mock_provider` — fixture returning a default `MockProvider()`
   - `mock_config` — minimal config dict
   - `tmp_dir` — alias for `tmp_path`, use for file-based tests

2. **Check for existing test file** at the mirror path (see Step 4 path rule). If it exists, read it to understand current coverage and style — extend rather than overwrite.

## Step 3 — Design Test Cases

List test scenarios before writing code. Cover three categories:

| Category | Examples |
|---|---|
| **Happy path** | Normal input → expected output |
| **Error / failure** | Invalid input, missing params, API errors → graceful error |
| **Edge cases** | Empty input, huge input, concurrent calls, boundary values |

For each scenario, write a one-line description:
```
- test_bash_echo: simple command returns stdout
- test_bash_exit_code: non-zero exit → is_error=True
- test_bash_timeout: long command + short timeout → timeout error
```

## Step 4 — Generate Test Code

### Path convention

Source `ohmycode/X/Y.py` → Test `tests/X/test_Y.py`

Examples:
- `ohmycode/tools/bash.py` → `tests/tools/test_bash.py`
- `ohmycode/core/loop.py` → `tests/core/test_loop.py`
- `ohmycode/providers/openai.py` → `tests/providers/test_openai_provider.py`

Ensure `tests/X/__init__.py` exists (create empty if needed).

### Project rules

- **Async tests**: decorate with `@pytest.mark.asyncio`
- **No network calls**: mock all HTTP / API interactions
- **File isolation**: use `tmp_path` or `tmp_dir` fixture for any file I/O
- **No hardcoded paths**: everything relative or via `tmp_path`
- **Minimal mocking**: prefer real objects with fake data over deep mock chains
- **One assert focus**: each test function tests one logical behavior

### Template — Tool test

```python
import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.<module> import <ToolClass>

@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)

@pytest.mark.asyncio
async def test_<tool>_basic(ctx):
    tool = <ToolClass>()
    result = await tool.execute({"param": "value"}, ctx)
    assert not result.is_error
    assert "expected" in result.output

@pytest.mark.asyncio
async def test_<tool>_error(ctx):
    tool = <ToolClass>()
    result = await tool.execute({"bad_param": ""}, ctx)
    assert result.is_error
```

### Template — Core module test

```python
import pytest
from ohmycode.config.config import OhMyCodeConfig
from ohmycode.core.<module> import <Class>

@pytest.mark.asyncio
async def test_<feature>_happy_path(mock_provider):
    config = OhMyCodeConfig(provider="mock", model="test", mode="auto", api_key="x")
    obj = <Class>(config=config)
    obj._provider = mock_provider
    # setup and assertions ...

@pytest.mark.asyncio
async def test_<feature>_error(mock_provider):
    # test error handling path
    ...
```

### Template — Provider test

```python
import pytest
from ohmycode.providers.base import PROVIDER_REGISTRY

def test_<provider>_is_registered():
    import ohmycode.providers.<module>  # noqa: F401
    assert "<provider_name>" in PROVIDER_REGISTRY

def test_<provider>_instantiation():
    from ohmycode.providers.<module> import <ProviderClass>
    provider = <ProviderClass>(api_key="test-key", base_url="http://localhost:8080/v1")
    assert provider.name == "<provider_name>"
```

## Step 5 — Run and Verify → hand off to `/run-tests`

After writing the test file, **immediately use `/run-tests`** to execute and verify:

1. Run the new tests: `/run-tests X/Y` (e.g., `/run-tests tools/bash`)
2. `/run-tests` will handle: execution, failure analysis, regression check

If `/run-tests` reports failures:
- **Test bug** → fix the test code, re-run `/run-tests`
- **Implementation bug** → fix the source code, re-run `/run-tests`
- Loop until all green ✓

## Quality Checklist

Before finishing, verify:

- [ ] Happy path, error, and edge cases all covered
- [ ] No hardcoded absolute paths — `tmp_path` used for file I/O
- [ ] Fixtures from `conftest.py` reused where applicable
- [ ] No real network calls — APIs mocked or faked
- [ ] Async tests have `@pytest.mark.asyncio`
- [ ] Test file at correct mirror path with `__init__.py`
- [ ] Each test name clearly describes what it verifies
- [ ] `/run-tests` confirms: new tests pass + full suite has no regressions

## Next Step

→ **`/run-tests`** — always run tests after generating them
