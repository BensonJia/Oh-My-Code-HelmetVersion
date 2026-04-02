---
name: add-feature
description: Guide for adding a new feature to OhMyCode. Use when user wants to add functionality that goes beyond existing extension points (tools/providers). Always start by reading docs/DEVELOPMENT_GUIDE.md.
---

# Add a New Feature to OhMyCode

Add a major new capability that isn't covered by existing extension points (add-tool, add-provider).

Examples: hook system, MCP support, multi-session management, plugin architecture, new CLI commands, new compression strategy.

## When to Use

- User wants a feature that requires new modules or modifying core modules
- User says "add hook support", "add MCP", "add plugin system", etc.
- The feature doesn't fit into the existing tool/provider/config pattern

## IMPORTANT: Read First

**Before doing anything, read `docs/DEVELOPMENT_GUIDE.md`** — it contains:
- Project architecture and module dependency graph
- Code conventions (file size limits, naming, async patterns)
- Testing conventions
- Commit conventions

## Step-by-Step Guide

### Step 1: Understand the Request

Ask the user:
1. What does the feature do?
2. Who uses it? (end users via CLI? developers extending OhMyCode? both?)
3. What existing modules does it interact with?

### Step 2: Design the Architecture

Based on `docs/DEVELOPMENT_GUIDE.md`, determine:

1. **Where does the code go?**
   - New module under `ohmycode/`? (e.g., `ohmycode/hooks/`)
   - Extends an existing module? (e.g., add to `ohmycode/core/`)
   - Both?

2. **What interfaces does it expose?**
   - New Protocol/ABC?
   - New config options?
   - New CLI commands/flags?
   - New slash commands in REPL?

3. **What existing code needs to change?**
   - Check the dependency graph in DEVELOPMENT_GUIDE.md
   - Minimize changes to existing modules
   - Never introduce circular imports

4. **Propose the design to the user** before writing code.

### Step 3: Implement with TDD

For each component:
1. Write failing test in `tests/<module>/test_<component>.py`
2. Run test to confirm it fails
3. Implement the minimal code to pass
4. Run ALL tests to ensure no regressions: `python3 -m pytest tests/ -v`
5. Commit incrementally

### Step 4: Integrate

If the feature requires changes to existing modules:
- Keep changes minimal and surgical
- Prefer adding new functions over modifying existing ones
- Use feature flags in config if the feature should be optional

### Step 5: Update Documentation

Update `docs/DEVELOPMENT_GUIDE.md` if the feature:
- Adds a new module to the architecture diagram
- Creates a new extension point
- Changes the module dependency graph
- Adds new config options

### Step 6: Final Verification

```bash
python3 -m pytest tests/ -v                # All tests pass
ohmycode -p "Test the new feature" --mode auto  # End-to-end works
```

## Architecture Constraints

From `docs/DEVELOPMENT_GUIDE.md`:

- **Single file < 500 lines** — split if larger
- **Single function < 50 lines** — extract helpers
- **No circular imports** — check the dependency graph
- **Async-first** — use `async/await` for I/O operations
- **Errors as values** — return error results, don't raise exceptions in tool/provider code
- **Config for behavior** — use `config.json` for user-facing settings, not hardcoded values

## Module Dependency Rules

```
cli.py → core/loop.py → providers/base.py
                       → tools/base.py
                       → core/context.py
                       → core/system_prompt.py
```

New modules should fit into this hierarchy. Leaf modules (no dependencies on other ohmycode modules) are safest. Modules that need to touch `core/loop.py` require extra care.

## Common Mistakes

- Modifying `core/loop.py` without understanding the async generator pattern
- Adding imports to `permissions.py` from `tools/base.py` (circular dependency)
- Not updating `DEVELOPMENT_GUIDE.md` after adding a new module
- Implementing without tests first
- Making a feature mandatory when it should be optional (use config flags)
