---
name: run-tests
description: Run tests and analyze results for OhMyCode. Use when user wants to run, check, or verify tests — or after any code change.
---

# Run Tests for OhMyCode

Run the project test suite, analyze results, and take action on failures.

This skill is part of the **OhMyCode development closed-loop**:

```
编码 ──→ /gen-tests ──→ /run-tests ──→ 分析失败 ──→ 修代码 ──╮
 ↑                                                            │
 ╰────────────────────────────────────────────────────────────╯
```

## When to Use

- After `/gen-tests` generates new test files — **verify them immediately**
- After editing any source code in `ohmycode/` — catch regressions
- After fixing a bug found by a previous `/run-tests` — confirm the fix
- Before committing — full suite gate
- User says "run tests", "check tests", "verify tests"

## Input

`$ARGUMENTS` — optional scope specifier. If empty, run the full suite.

| Argument | pytest path |
|---|---|
| *(empty)* | `tests/` (full suite) |
| `tools` | `tests/tools/` |
| `tools/bash` | `tests/tools/test_bash.py` |
| `core` | `tests/core/` |
| `core/loop` | `tests/core/test_loop.py` |
| `providers` | `tests/providers/` |
| `config` | `tests/config/` |
| `skills` | `tests/skills/` |
| specific file path | use as-is |

## Step 1 — Determine Scope

Resolve `$ARGUMENTS` to a pytest target path using the table above.

If a specific file is given, verify it exists. If not, check for the closest match under `tests/`.

## Step 2 — Run Tests

```bash
python3 -m pytest <resolved_path> -v --tb=short 2>&1 | tee tests_run.log
```

Use `-v` for verbose output and `--tb=short` for concise tracebacks.

## Step 3 — Analyze Results

### All passed

Report the result summary (e.g., "73 passed in 2.1s") and confirm the code is healthy. No further action needed.

### Failures detected — enter fix loop

For each failure:

1. **Read the traceback** from the test output
2. **Classify the root cause**:
   - **Test bug** — the test itself has a wrong assertion or outdated expectation
   - **Implementation bug** — the source code under test has a defect
   - **Environment issue** — missing dependency, import error, fixture mismatch
3. **Fix it**:
   - For test bugs: fix the test code directly
   - For implementation bugs: fix the source code in `ohmycode/`
   - For environment issues: install missing deps or fix config
4. **Re-run `/run-tests`** — repeat until all green ✓

This is the core of the closed-loop: **fail → diagnose → fix → re-run → pass**.

### Warnings

Review warnings in the output. Common ones:

| Warning | Action |
|---|---|
| `PytestUnraisableExceptionWarning` | Usually async cleanup — check for missing `await` |
| `DeprecationWarning` | Note for future cleanup, not blocking |
| `RuntimeWarning: coroutine was never awaited` | Missing `await` — fix immediately |

Ignore warnings that don't affect correctness unless they indicate real bugs.

## Step 4 — Regression Check

If Step 2 only ran a subset of tests, prompt to run the full suite:

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tee tests_run.log
```

This catches regressions in other modules caused by the recent change. The task is not complete until the full suite passes.

## Development Loop Checkpoints

Use `/run-tests` at every transition in the closed-loop:

| When | What to do |
|---|---|
| After `/gen-tests` | Run new tests to verify they pass |
| After editing `ohmycode/` source | Catch regressions early |
| After fixing a failure | Confirm the fix, re-enter loop if still red |
| Before committing | Full suite gate — `python3 -m pytest tests/ -v` must be all green |
| When resuming work | Baseline health check |

## Related Skills

- **`/gen-tests`** — generates tests; always follow up with `/run-tests`
- **`/commit-conventions`** — commit after all tests pass
