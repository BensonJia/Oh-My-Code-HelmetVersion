"""Benchmark task definitions — SWE-bench style coding challenges for OhMyCode."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class BenchTask:
    name: str
    category: str  # "code-gen" | "bug-fix" | "test-gen" | "refactor" | "tool-use"
    prompt: str
    setup: Callable[[Path], None]  # prepare files in tmp_dir
    validate: Callable[[Path], tuple[bool, str]]  # (passed, reason)
    max_turns: int = 15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_py(cwd: Path, code: str) -> tuple[int, str]:
    r = subprocess.run(
        ["python3", "-c", code], capture_output=True, text=True, cwd=str(cwd), timeout=30,
    )
    return r.returncode, r.stdout + r.stderr


def _run_pytest(cwd: Path, path: str = ".") -> tuple[int, str]:
    r = subprocess.run(
        ["python3", "-m", "pytest", path, "-v", "--tb=short"],
        capture_output=True, text=True, cwd=str(cwd), timeout=60,
    )
    return r.returncode, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# Task 1: fibonacci (code generation, simple)
# ---------------------------------------------------------------------------

def _setup_fib(d: Path):
    pass  # empty dir — agent must create everything

def _validate_fib(d: Path) -> tuple[bool, str]:
    fib_file = d / "fib.py"
    if not fib_file.exists():
        return False, "fib.py not created"
    rc, out = _run_py(d, "from fib import fib; assert fib(0)==0; assert fib(1)==1; assert fib(10)==55; print('OK')")
    if rc != 0:
        return False, f"fib() wrong output: {out[:200]}"
    return True, "fib.py correct"


# ---------------------------------------------------------------------------
# Task 2: bug-fix (debugging)
# ---------------------------------------------------------------------------

def _setup_bugfix(d: Path):
    (d / "calc.py").write_text(
        "def divide(a: float, b: float) -> float:\n"
        "    \"\"\"Return a / b, rounded to 2 decimals.\"\"\"\n"
        "    return round(a / b, 1)  # BUG: should be round(..., 2)\n"
    )
    (d / "test_calc.py").write_text(
        "from calc import divide\n\n"
        "def test_divide_basic():\n"
        "    assert divide(10, 3) == 3.33\n\n"
        "def test_divide_exact():\n"
        "    assert divide(10, 2) == 5.0\n"
    )

def _validate_bugfix(d: Path) -> tuple[bool, str]:
    rc, out = _run_pytest(d, "test_calc.py")
    if rc != 0:
        return False, f"test_calc.py still failing: {out[:200]}"
    return True, "bug fixed, tests pass"


# ---------------------------------------------------------------------------
# Task 3: test generation
# ---------------------------------------------------------------------------

def _setup_testgen(d: Path):
    (d / "utils.py").write_text(
        "def clamp(value: float, lo: float, hi: float) -> float:\n"
        "    return max(lo, min(value, hi))\n\n"
        "def slugify(text: str) -> str:\n"
        "    import re\n"
        "    text = text.lower().strip()\n"
        "    text = re.sub(r'[^\\w\\s-]', '', text)\n"
        "    return re.sub(r'[\\s_]+', '-', text)\n\n"
        "def chunk_list(lst: list, size: int) -> list:\n"
        "    return [lst[i:i+size] for i in range(0, len(lst), size)]\n"
    )

def _validate_testgen(d: Path) -> tuple[bool, str]:
    test_files = list(d.glob("test_*.py"))
    if not test_files:
        return False, "no test file created"
    rc, out = _run_pytest(d)
    if rc != 0:
        return False, f"generated tests fail: {out[:200]}"
    # Check minimum coverage: at least 3 test functions (one per util func)
    test_content = test_files[0].read_text()
    test_count = test_content.count("def test_")
    if test_count < 3:
        return False, f"only {test_count} tests, expected ≥3"
    return True, f"{test_count} tests generated, all pass"


# ---------------------------------------------------------------------------
# Task 4: refactor (preserve behavior)
# ---------------------------------------------------------------------------

def _setup_refactor(d: Path):
    (d / "process.py").write_text(
        "def process_data(data):\n"
        "    result = []\n"
        "    for item in data:\n"
        "        if type(item) == str:\n"
        "            if len(item) > 0:\n"
        "                if item[0].isupper():\n"
        "                    result.append(item.lower())\n"
        "                else:\n"
        "                    result.append(item.upper())\n"
        "            else:\n"
        "                result.append(item)\n"
        "        elif type(item) == int:\n"
        "            if item > 0:\n"
        "                result.append(item * 2)\n"
        "            else:\n"
        "                result.append(0)\n"
        "        else:\n"
        "            result.append(item)\n"
        "    return result\n"
    )
    (d / "test_process.py").write_text(
        "from process import process_data\n\n"
        "def test_uppercase_to_lower():\n"
        "    assert process_data(['Hello']) == ['hello']\n\n"
        "def test_lowercase_to_upper():\n"
        "    assert process_data(['world']) == ['WORLD']\n\n"
        "def test_empty_string():\n"
        "    assert process_data(['']) == ['']\n\n"
        "def test_positive_int():\n"
        "    assert process_data([5]) == [10]\n\n"
        "def test_negative_int():\n"
        "    assert process_data([-3]) == [0]\n\n"
        "def test_mixed():\n"
        "    assert process_data(['Hi', 'lo', 7, -1]) == ['hi', 'LO', 14, 0]\n"
    )

def _validate_refactor(d: Path) -> tuple[bool, str]:
    rc, out = _run_pytest(d, "test_process.py")
    if rc != 0:
        return False, f"refactor broke tests: {out[:200]}"
    code = (d / "process.py").read_text()
    if "type(item) ==" in code:
        return False, "code not refactored (still uses type() ==)"
    return True, "refactored and tests still pass"


# ---------------------------------------------------------------------------
# Task 5: search-and-replace across files
# ---------------------------------------------------------------------------

def _setup_grep_replace(d: Path):
    (d / "app.py").write_text(
        "from api import old_api_call\n\n"
        "def main():\n"
        "    result = old_api_call('/users')\n"
        "    return result\n"
    )
    (d / "worker.py").write_text(
        "from api import old_api_call\n\n"
        "def run_job(job_id):\n"
        "    return old_api_call(f'/jobs/{job_id}')\n"
    )
    (d / "api.py").write_text(
        "def old_api_call(endpoint: str) -> dict:\n"
        "    return {'endpoint': endpoint, 'status': 'ok'}\n\n"
        "def new_api_call(endpoint: str) -> dict:\n"
        "    return {'endpoint': endpoint, 'status': 'ok', 'version': 2}\n"
    )

def _validate_grep_replace(d: Path) -> tuple[bool, str]:
    for fname in ("app.py", "worker.py"):
        content = (d / fname).read_text()
        if "old_api_call" in content:
            return False, f"{fname} still uses old_api_call"
        if "new_api_call" not in content:
            return False, f"{fname} missing new_api_call"
    return True, "all files migrated to new_api_call"


# ---------------------------------------------------------------------------
# Task 6: create module + tests from scratch
# ---------------------------------------------------------------------------

def _setup_stack(d: Path):
    pass  # empty dir

def _validate_stack(d: Path) -> tuple[bool, str]:
    if not (d / "stack.py").exists():
        return False, "stack.py not created"
    test_files = list(d.glob("test_*.py"))
    if not test_files:
        return False, "no test file created"
    # Validate Stack class works
    rc, out = _run_py(d, (
        "from stack import Stack; s = Stack(); "
        "s.push(1); s.push(2); "
        "assert s.peek() == 2; "
        "assert s.pop() == 2; "
        "assert s.pop() == 1; "
        "assert s.is_empty(); "
        "print('OK')"
    ))
    if rc != 0:
        return False, f"Stack class broken: {out[:200]}"
    rc, out = _run_pytest(d)
    if rc != 0:
        return False, f"tests fail: {out[:200]}"
    return True, "Stack module + tests all pass"


# ---------------------------------------------------------------------------
# Task 7: type-error fix
# ---------------------------------------------------------------------------

def _setup_type_error(d: Path):
    (d / "transform.py").write_text(
        "def transform(items: list) -> list[str]:\n"
        "    \"\"\"Convert all items to uppercase strings.\"\"\"\n"
        "    return [item.upper() for item in items]  # crashes on non-str\n"
    )
    (d / "test_transform.py").write_text(
        "from transform import transform\n\n"
        "def test_strings():\n"
        "    assert transform(['hello', 'world']) == ['HELLO', 'WORLD']\n\n"
        "def test_mixed_types():\n"
        "    assert transform(['hello', 42, None, 3.14]) == ['HELLO', '42', 'NONE', '3.14']\n"
    )

def _validate_type_error(d: Path) -> tuple[bool, str]:
    rc, out = _run_pytest(d, "test_transform.py")
    if rc != 0:
        return False, f"tests still fail: {out[:200]}"
    return True, "type error fixed, all tests pass"


# ---------------------------------------------------------------------------
# Task 8: read-and-answer (comprehension, no file mutation)
# ---------------------------------------------------------------------------

def _setup_comprehend(d: Path):
    (d / "mystery.py").write_text(
        "def mystery(n: int) -> list[int]:\n"
        "    if n <= 0:\n"
        "        return []\n"
        "    sieve = [True] * (n + 1)\n"
        "    sieve[0] = sieve[1] = False\n"
        "    for i in range(2, int(n**0.5) + 1):\n"
        "        if sieve[i]:\n"
        "            for j in range(i*i, n + 1, i):\n"
        "                sieve[j] = False\n"
        "    return [i for i, is_p in enumerate(sieve) if is_p]\n"
    )
    # Write the expected-answer hint for validation
    (d / ".answer_keywords").write_text("prime,sieve")

def _validate_comprehend(d: Path) -> tuple[bool, str]:
    answer_file = d / "answer.txt"
    if not answer_file.exists():
        # Check if the agent wrote its answer to any .txt or .md file
        for f in d.iterdir():
            if f.suffix in (".txt", ".md") and f.name != ".answer_keywords":
                answer_file = f
                break
    if not answer_file.exists():
        return False, "no answer file found (expected answer.txt)"
    answer = answer_file.read_text().lower()
    keywords = (d / ".answer_keywords").read_text().strip().split(",")
    found = [kw for kw in keywords if kw in answer]
    if len(found) < len(keywords):
        missing = [kw for kw in keywords if kw not in answer]
        return False, f"answer missing keywords: {missing}"
    return True, "correctly identified as prime sieve"


# ===========================================================================
# Full suite
# ===========================================================================

BENCH_SUITE: list[BenchTask] = [
    BenchTask(
        name="fibonacci",
        category="code-gen",
        prompt=(
            "Create a file `fib.py` in the current directory with a function `fib(n)` "
            "that returns the n-th Fibonacci number (0-indexed: fib(0)=0, fib(1)=1, fib(10)=55)."
        ),
        setup=_setup_fib,
        validate=_validate_fib,
        max_turns=8,
    ),
    BenchTask(
        name="bug-fix-round",
        category="bug-fix",
        prompt=(
            "The file `test_calc.py` is failing. Read `calc.py` and `test_calc.py`, "
            "find the bug, and fix it so all tests pass."
        ),
        setup=_setup_bugfix,
        validate=_validate_bugfix,
        max_turns=10,
    ),
    BenchTask(
        name="test-generation",
        category="test-gen",
        prompt=(
            "Read `utils.py` and write comprehensive tests in `test_utils.py`. "
            "Cover happy paths, edge cases, and error cases for all three functions."
        ),
        setup=_setup_testgen,
        validate=_validate_testgen,
        max_turns=10,
    ),
    BenchTask(
        name="refactor-preserve",
        category="refactor",
        prompt=(
            "Refactor `process.py` to be more Pythonic and readable. "
            "Use isinstance() instead of type(), reduce nesting. "
            "All tests in `test_process.py` must still pass."
        ),
        setup=_setup_refactor,
        validate=_validate_refactor,
        max_turns=10,
    ),
    BenchTask(
        name="grep-replace",
        category="tool-use",
        prompt=(
            "The codebase uses `old_api_call` which is deprecated. "
            "Replace ALL usages of `old_api_call` with `new_api_call` in `app.py` and `worker.py`. "
            "Update the imports too. Do NOT modify `api.py`."
        ),
        setup=_setup_grep_replace,
        validate=_validate_grep_replace,
        max_turns=10,
    ),
    BenchTask(
        name="stack-module",
        category="code-gen",
        prompt=(
            "Create `stack.py` with a Stack class (methods: push, pop, peek, is_empty) "
            "and `test_stack.py` with comprehensive tests. All tests must pass."
        ),
        setup=_setup_stack,
        validate=_validate_stack,
        max_turns=10,
    ),
    BenchTask(
        name="type-error-fix",
        category="bug-fix",
        prompt=(
            "Running `pytest test_transform.py` fails because `transform()` crashes on non-string items. "
            "Fix `transform.py` so it converts any item to a string first, then uppercases it. "
            "All tests in `test_transform.py` must pass."
        ),
        setup=_setup_type_error,
        validate=_validate_type_error,
        max_turns=10,
    ),
    BenchTask(
        name="code-comprehension",
        category="comprehension",
        prompt=(
            "Read `mystery.py` and write a file `answer.txt` explaining what the `mystery` function does. "
            "Include the algorithm name."
        ),
        setup=_setup_comprehend,
        validate=_validate_comprehend,
        max_turns=8,
    ),
]
