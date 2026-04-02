# Docker Sandbox And Safety Pause Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Force high-risk tool execution through a Docker-backed sandbox and pause execution when pre-execution safety review flags risky actions.

**Architecture:** Add a runtime abstraction that tools use instead of touching the host directly, then provide a Docker-backed runtime that maps the project into an isolated `/workspace`. Add a `SafetyEngine` in the conversation loop after permission checks and before tool execution, emitting pause events for the CLI to render and approve.

**Tech Stack:** Python 3.9+, asyncio, Docker CLI, pytest, pytest-asyncio, pydantic

---

### Task 1: Add Config And Runtime Interfaces

**Files:**
- Create: `ohmycode/runtime/base.py`
- Create: `ohmycode/runtime/__init__.py`
- Modify: `ohmycode/config/config.py`
- Test: `tests/runtime/test_base.py`

**Step 1: Write the failing test**

Add tests asserting config exposes sandbox settings and runtime objects provide workspace path translation.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runtime/test_base.py -v`
Expected: FAIL because runtime module does not exist.

**Step 3: Write minimal implementation**

Create runtime protocol/dataclasses and config models for `sandbox` and `safety`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runtime/test_base.py -v`
Expected: PASS

### Task 2: Add Docker Runtime

**Files:**
- Create: `ohmycode/runtime/docker.py`
- Test: `tests/runtime/test_docker.py`

**Step 1: Write the failing test**

Add tests for Docker command generation, path resolution to `/workspace`, and exec/read/write/edit/glob/grep methods using a fake command runner.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runtime/test_docker.py -v`
Expected: FAIL because Docker runtime is missing.

**Step 3: Write minimal implementation**

Implement Docker-backed runtime with bounded resources, project bind mount, and command helpers.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runtime/test_docker.py -v`
Expected: PASS

### Task 3: Route Risky Tools Through Runtime

**Files:**
- Modify: `ohmycode/tools/base.py`
- Modify: `ohmycode/tools/bash.py`
- Modify: `ohmycode/tools/read.py`
- Modify: `ohmycode/tools/write.py`
- Modify: `ohmycode/tools/edit.py`
- Modify: `ohmycode/tools/glob_tool.py`
- Modify: `ohmycode/tools/grep.py`
- Test: `tests/tools/test_bash.py`
- Test: `tests/tools/test_read.py`
- Test: `tests/tools/test_write.py`
- Test: `tests/tools/test_edit.py`
- Test: `tests/tools/test_glob.py`
- Test: `tests/tools/test_grep.py`

**Step 1: Write the failing test**

Update tool tests so they assert tool methods use a runtime object rather than the host filesystem/process.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_bash.py tests/tools/test_read.py tests/tools/test_write.py tests/tools/test_edit.py tests/tools/test_glob.py tests/tools/test_grep.py -v`
Expected: FAIL because ToolContext has no runtime and tools still touch host resources.

**Step 3: Write minimal implementation**

Extend `ToolContext` with runtime metadata and swap direct host access for runtime calls.

**Step 4: Run test to verify it passes**

Run: same pytest command
Expected: PASS

### Task 4: Build Safety Engine And Pause Events

**Files:**
- Create: `ohmycode/core/safety.py`
- Modify: `ohmycode/core/messages.py`
- Modify: `ohmycode/core/loop.py`
- Test: `tests/core/test_safety.py`
- Test: `tests/core/test_loop.py`

**Step 1: Write the failing test**

Add tests for risk classification and for `ConversationLoop` yielding a pause/alert event when safety review requires approval.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_safety.py tests/core/test_loop.py -v`
Expected: FAIL because safety engine and pause events do not exist.

**Step 3: Write minimal implementation**

Add deterministic rule checks, pause event dataclasses, approval callback support, and integration in `run_turn()`.

**Step 4: Run test to verify it passes**

Run: same pytest command
Expected: PASS

### Task 5: Wire CLI And Loop Initialization

**Files:**
- Modify: `ohmycode/cli.py`
- Modify: `ohmycode/core/loop.py`
- Modify: `ohmycode/core/system_prompt.py`
- Test: `tests/core/test_system_prompt.py`
- Test: `tests/cli/test_render_stream.py`

**Step 1: Write the failing test**

Add tests for CLI rendering of safety alerts and prompt text that describes sandbox mode.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_system_prompt.py tests/cli/test_render_stream.py -v`
Expected: FAIL because sandbox and safety information is not rendered.

**Step 3: Write minimal implementation**

Initialize runtime/safety engine in the loop and render alerts in CLI output.

**Step 4: Run test to verify it passes**

Run: same pytest command
Expected: PASS

### Task 6: Update Docs And Verify

**Files:**
- Modify: `agent_docs/ARCHITECTURE.md`
- Modify: `agent_docs/KEY-MODULES.md`
- Modify: `docs/DEVELOPMENT_GUIDE.md`

**Step 1: Run focused verification**

Run: `python -m pytest tests/runtime/test_base.py tests/runtime/test_docker.py tests/core/test_safety.py tests/core/test_loop.py tests/tools/test_bash.py tests/tools/test_read.py tests/tools/test_write.py tests/tools/test_edit.py tests/tools/test_glob.py tests/tools/test_grep.py -v`
Expected: PASS

**Step 2: Run broader regression suite**

Run: `python -m pytest tests/ -v`
Expected: PASS

**Step 3: Commit**

```bash
git add docs/plans/2026-04-03-docker-sandbox-safety.md ohmycode tests agent_docs docs/DEVELOPMENT_GUIDE.md
git commit -m "feat(core): add docker sandbox and safety pauses"
```
