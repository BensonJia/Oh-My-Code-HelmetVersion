#!/usr/bin/env python3
"""OhMyCode Benchmark Runner — one command to score any provider/model.

Usage:
    python3 benchmarks/run_bench.py                     # full suite
    python3 benchmarks/run_bench.py --tasks fib,bug     # specific tasks (name substring)
    python3 benchmarks/run_bench.py --provider openai --model gpt-4o
    python3 benchmarks/run_bench.py --dry-run            # validate tasks without LLM
"""

from __future__ import annotations

# ── Configurable constants ──────────────────────────────────────────────────
OUTPUT_JSON = "bench_results.json"
OUTPUT_LOG = "bench_run.log"
MAX_TURNS_DEFAULT = 15
# ────────────────────────────────────────────────────────────────────────────

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.suite import BENCH_SUITE, BenchTask
from ohmycode.config.config import load_config, OhMyCodeConfig
from ohmycode.core.loop import ConversationLoop
from ohmycode.core.messages import TextChunk, ToolCallStart, ToolCallResult, TurnComplete


@dataclass
class TaskResult:
    name: str
    category: str
    passed: bool
    reason: str
    tokens_in: int
    tokens_out: int
    duration_s: float
    turns: int
    error: str = ""


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

async def run_one_task(task: BenchTask, config: OhMyCodeConfig) -> TaskResult:
    """Execute a single benchmark task, return result with token tracking."""
    with tempfile.TemporaryDirectory(prefix=f"bench_{task.name}_") as tmp:
        tmp_dir = Path(tmp)
        task.setup(tmp_dir)

        # Override cwd for the loop
        orig_cwd = os.getcwd()
        os.chdir(tmp_dir)

        tokens_in = 0
        tokens_out = 0
        turns = 0
        t0 = time.monotonic()

        try:
            conv = ConversationLoop(config=config)
            conv.initialize()
            conv._system_prompt = (
                "You are a coding assistant. You have tools to read, write, edit files "
                "and run bash commands. Complete the task. Work in the current directory."
            )
            conv.add_user_message(task.prompt)

            # Multi-turn loop: run_turn() handles tool calls internally
            # but yields TurnComplete per LLM call. If finish_reason == "tool_use",
            # the loop inside run_turn() continues automatically.
            async for event in conv.run_turn():
                if isinstance(event, TurnComplete):
                    tokens_in += event.usage.prompt_tokens
                    tokens_out += event.usage.completion_tokens
                    turns += 1

            elapsed = time.monotonic() - t0
            passed, reason = task.validate(tmp_dir)
            return TaskResult(
                name=task.name, category=task.category,
                passed=passed, reason=reason,
                tokens_in=tokens_in, tokens_out=tokens_out,
                duration_s=round(elapsed, 2), turns=turns,
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            return TaskResult(
                name=task.name, category=task.category,
                passed=False, reason="exception",
                tokens_in=tokens_in, tokens_out=tokens_out,
                duration_s=round(elapsed, 2), turns=turns,
                error=str(exc)[:300],
            )
        finally:
            os.chdir(orig_cwd)


def run_unit_tests() -> dict:
    """Run project unit tests, return summary."""
    r = subprocess.run(
        ["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=120,
    )
    lines = r.stdout.strip().splitlines()
    summary_line = lines[-1] if lines else ""
    passed = r.returncode == 0
    return {
        "passed": passed,
        "summary": summary_line,
        "returncode": r.returncode,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(
    unit_result: dict,
    task_results: list[TaskResult],
    config: OhMyCodeConfig,
    total_time: float,
):
    total_in = sum(r.tokens_in for r in task_results)
    total_out = sum(r.tokens_out for r in task_results)
    passed = sum(1 for r in task_results if r.passed)
    total = len(task_results)

    sep = "─" * 72
    print(f"\n{sep}")
    print(f"  OhMyCode Benchmark Report")
    print(f"{sep}")
    print(f"  Provider:  {config.provider}")
    print(f"  Model:     {config.model}")
    print(f"  Mode:      {config.mode}")
    print(f"{sep}\n")

    # Unit tests
    unit_icon = "✅" if unit_result["passed"] else "❌"
    print(f"  Unit Tests: {unit_icon}  {unit_result['summary']}\n")

    # Task results table
    print(f"  {'Task':<22} {'Cat':<14} {'Pass':>4}  {'Tokens In':>10} {'Tokens Out':>11} {'Time':>6}  Reason")
    print(f"  {'─'*22} {'─'*14} {'─'*4}  {'─'*10} {'─'*11} {'─'*6}  {'─'*20}")

    for r in task_results:
        icon = "✅" if r.passed else "❌"
        tok_in = f"{r.tokens_in:,}" if r.tokens_in else "-"
        tok_out = f"{r.tokens_out:,}" if r.tokens_out else "-"
        time_s = f"{r.duration_s:.1f}s"
        reason = r.reason[:30]
        if r.error:
            reason = f"ERR: {r.error[:25]}"
        print(f"  {r.name:<22} {r.category:<14} {icon:>4}  {tok_in:>10} {tok_out:>11} {time_s:>6}  {reason}")

    print(f"\n{sep}")
    print(f"  Score:      {passed}/{total} tasks passed")
    print(f"  Tokens:     {total_in:,} in  /  {total_out:,} out  /  {total_in + total_out:,} total")
    print(f"  Time:       {total_time:.1f}s total")
    print(f"{sep}\n")


def save_json(unit_result: dict, task_results: list[TaskResult], config: OhMyCodeConfig):
    data = {
        "provider": config.provider,
        "model": config.model,
        "unit_tests": unit_result,
        "tasks": [
            {
                "name": r.name, "category": r.category,
                "passed": r.passed, "reason": r.reason,
                "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                "duration_s": r.duration_s, "turns": r.turns,
                "error": r.error,
            }
            for r in task_results
        ],
        "totals": {
            "passed": sum(1 for r in task_results if r.passed),
            "total": len(task_results),
            "tokens_in": sum(r.tokens_in for r in task_results),
            "tokens_out": sum(r.tokens_out for r in task_results),
        },
    }
    out_path = PROJECT_ROOT / OUTPUT_JSON
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  Results saved to: {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="OhMyCode Benchmark Runner")
    p.add_argument("--tasks", help="Comma-separated task name substrings to run (default: all)")
    p.add_argument("--provider", help="Override provider")
    p.add_argument("--model", help="Override model")
    p.add_argument("--api-key", dest="api_key", help="Override API key")
    p.add_argument("--base-url", dest="base_url", help="Override base URL")
    p.add_argument("--skip-unit", action="store_true", help="Skip unit test phase")
    p.add_argument("--dry-run", action="store_true", help="Validate task setup/validate without LLM")
    return p.parse_args()


def filter_tasks(tasks: list[BenchTask], filter_str: str | None) -> list[BenchTask]:
    if not filter_str:
        return tasks
    patterns = [p.strip().lower() for p in filter_str.split(",")]
    return [t for t in tasks if any(p in t.name.lower() for p in patterns)]


async def dry_run(tasks: list[BenchTask]):
    """Test setup/validate locally without calling LLM."""
    print(f"\n  Dry run: validating {len(tasks)} task definitions...\n")
    for task in tasks:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            task.setup(tmp_dir)
            files = [f.name for f in tmp_dir.iterdir()]
            passed, reason = task.validate(tmp_dir)
            # In dry-run, tasks that need agent work should FAIL validation
            icon = "⚙️" if not passed else "⚠️ (passes without agent?)"
            print(f"  {task.name:<22} files={files}  validate={icon}  {reason}")
    print()


async def main():
    args = parse_args()

    tasks = filter_tasks(BENCH_SUITE, args.tasks)
    if not tasks:
        print("No tasks matched the filter.")
        return

    if args.dry_run:
        await dry_run(tasks)
        return

    # Load config with CLI overrides
    overrides = {
        "provider": args.provider,
        "model": args.model,
        "api_key": args.api_key,
        "base_url": args.base_url,
        "mode": "auto",  # benchmarks always run in auto mode
    }
    config = load_config(overrides)

    print(f"\n  OhMyCode Benchmark — {config.provider}/{config.model}")
    print(f"  Tasks: {len(tasks)} selected\n")

    # Phase 1: unit tests
    unit_result = {"passed": True, "summary": "(skipped)", "returncode": 0}
    if not args.skip_unit:
        print("  Phase 1: Running unit tests...")
        unit_result = run_unit_tests()
        icon = "✅" if unit_result["passed"] else "❌"
        print(f"  {icon} {unit_result['summary']}\n")

    # Phase 2: agent tasks
    print(f"  Phase 2: Running {len(tasks)} agent tasks...\n")
    task_results: list[TaskResult] = []
    t_total = time.monotonic()

    for i, task in enumerate(tasks, 1):
        print(f"  [{i}/{len(tasks)}] {task.name} ({task.category})...", end=" ", flush=True)
        result = await run_one_task(task, config)
        task_results.append(result)
        icon = "✅" if result.passed else "❌"
        tok = f"{result.tokens_in + result.tokens_out:,}tok"
        print(f"{icon} {result.duration_s:.1f}s {tok}  {result.reason[:40]}")

    elapsed = time.monotonic() - t_total
    print_report(unit_result, task_results, config, elapsed)
    save_json(unit_result, task_results, config)


if __name__ == "__main__":
    asyncio.run(main())
