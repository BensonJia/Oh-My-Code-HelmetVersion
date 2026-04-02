---
name: bench
description: Run OhMyCode benchmarks — score any provider/model with token tracking. Use when user wants to benchmark, evaluate, test performance, or compare models.
---

# OhMyCode Benchmark

One-command benchmarking: run 8 SWE-bench-style coding tasks through OhMyCode, track token usage (in/out), and produce a scorecard.

Works with **any provider and model** — uses whatever is configured in `~/.ohmycode/config.json` or overridden via CLI args.

## When to Use

- User says "run benchmark", "bench", "score", "evaluate", "test performance"
- User wants to compare models or providers
- After major code changes, to verify agent capabilities still work

## Input

`$ARGUMENTS` — optional filters and overrides.

| Argument | Example | Effect |
|---|---|---|
| *(empty)* | `/bench` | Full suite, current config |
| task filter | `/bench fib,bug` | Only matching tasks |
| `--dry-run` | `/bench --dry-run` | Validate task definitions without LLM |

## Step 1 — Run the Benchmark

```bash
python3 benchmarks/run_bench.py $ARGUMENTS 2>&1 | tee bench_run.log
```

### Override provider/model for comparison

```bash
# Test with a different model
python3 benchmarks/run_bench.py --provider openai --model gpt-4o-mini 2>&1 | tee bench_run.log

# Test with Anthropic
python3 benchmarks/run_bench.py --provider anthropic --model claude-sonnet-4-20250514 2>&1 | tee bench_run.log

# Test with custom endpoint
python3 benchmarks/run_bench.py --base-url http://localhost:8080/v1 --api-key test 2>&1 | tee bench_run.log
```

## Step 2 — Read Results

The harness outputs:
1. **Terminal report** — table with per-task pass/fail, tokens, time
2. **`bench_results.json`** — machine-readable results for comparison

Key metrics to report:
- **Score**: X/8 tasks passed
- **Tokens in**: total prompt tokens across all tasks
- **Tokens out**: total completion tokens across all tasks
- **Total tokens**: in + out
- **Time**: wall-clock seconds

## Step 3 — Analyze Failures

If any tasks failed:
1. Read the `reason` column in the report
2. Check `bench_results.json` for the `error` field
3. Classify: is it a model capability issue, or an OhMyCode bug?
4. For OhMyCode bugs → fix and re-run `/bench` (closed-loop)

## Benchmark Tasks

| # | Task | Category | What It Tests |
|---|---|---|---|
| 1 | fibonacci | code-gen | Create a function from spec |
| 2 | bug-fix-round | bug-fix | Find and fix an off-by-one error |
| 3 | test-generation | test-gen | Write tests for existing code |
| 4 | refactor-preserve | refactor | Improve code without breaking tests |
| 5 | grep-replace | tool-use | Multi-file search and replace |
| 6 | stack-module | code-gen | Create module + tests from scratch |
| 7 | type-error-fix | bug-fix | Fix a TypeError in existing code |
| 8 | code-comprehension | comprehension | Read code and explain the algorithm |

## Adding New Tasks

Edit `benchmarks/suite.py`:

```python
BenchTask(
    name="your-task",
    category="bug-fix",
    prompt="The task description for the agent...",
    setup=lambda d: (d / "code.py").write_text("..."),  # prepare files
    validate=lambda d: (True, "reason"),                 # check result
    max_turns=10,
)
```

Then append to `BENCH_SUITE` list.

## Model Comparison Workflow

To compare two models:

```bash
python3 benchmarks/run_bench.py --model gpt-4o 2>&1 | tee bench_gpt4o.log
cp bench_results.json bench_gpt4o.json

python3 benchmarks/run_bench.py --model gpt-4o-mini 2>&1 | tee bench_mini.log
cp bench_results.json bench_mini.json
```

Then compare the JSON files for score and token efficiency.

## Related Skills

- **`/run-tests`** — run unit tests (the benchmark runs these too as Phase 1)
- **`/gen-tests`** — generate tests (task #3 in the benchmark tests this capability)
