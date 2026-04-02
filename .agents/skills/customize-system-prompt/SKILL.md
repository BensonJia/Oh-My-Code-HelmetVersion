---
name: customize-system-prompt
description: Guide for customizing OhMyCode's AI personality and behavior via system prompt. Use when user wants to change how the AI behaves, its tone, or its instructions.
---

# Customize OhMyCode's System Prompt

Change the AI assistant's personality, behavior rules, or domain expertise without writing code.

## When to Use

- User says "make it more formal", "act like a senior engineer", "focus on Python"
- User wants to add custom instructions or constraints
- User wants the AI to have domain-specific knowledge

## Three Ways to Customize

### Method 1: OHMYCODE.md (Per-Project, Recommended)

Create a `OHMYCODE.md` (or `CLAUDE.md`) file in your project root:

```markdown
# Project Instructions

You are working on a Django REST API project.

## Rules
- Always use type hints
- Prefer class-based views over function-based
- Write docstrings for all public functions
- Use Black formatting style

## Tech Stack
- Python 3.12, Django 5.0, PostgreSQL
- pytest for testing, factory_boy for fixtures
```

OhMyCode auto-detects this file and injects it into the system prompt.

**Scope:** Only applies when running `ohmycode` in this directory.

### Method 2: system_prompt_append (Global Config)

Add to `~/.ohmycode/config.json`:

```json
{
  "system_prompt_append": "Always respond in Chinese. Prefer simple solutions over clever ones. Never use global variables."
}
```

**Scope:** Applies to ALL conversations.

### Method 3: Modify system_prompt.py (Advanced)

Edit `ohmycode/core/system_prompt.py` → `build_system_prompt()` to change the base role description or add new sections.

**Scope:** Permanent change to the codebase.

## Examples

### Friendly Tutor
```markdown
# OHMYCODE.md
You are a patient coding tutor. Explain concepts step by step.
When the user makes a mistake, explain why it's wrong before showing the fix.
Use analogies to explain complex concepts.
```

### Strict Code Reviewer
```markdown
# OHMYCODE.md
You are a strict senior engineer doing code review.
Point out every issue: bugs, performance, readability, security.
Don't write code for the user — give them guidance to fix it themselves.
Rate code quality on a 1-10 scale.
```

### Domain Expert
```markdown
# OHMYCODE.md
You are an expert in machine learning with PyTorch.
When suggesting solutions, prefer PyTorch over TensorFlow.
Always consider GPU memory usage and training efficiency.
Reference relevant papers when explaining algorithms.
```

## How It Works

`ohmycode/core/system_prompt.py` → `build_system_prompt()` assembles the prompt in this order:

1. **Base role** — hardcoded AI assistant description
2. **Project instructions** — from `OHMYCODE.md` / `CLAUDE.md` (found via `find_project_instructions()`)
3. **Memory** — from `~/.ohmycode/memory/MEMORY.md`
4. **Environment** — working directory, OS, shell, Python version
5. **Mode** — permission mode description
6. **Tools** — available tool list
7. **Append** — from `config.system_prompt_append`

## Tips

- Keep `OHMYCODE.md` focused — don't repeat what's already in the base prompt
- Use Markdown headers to organize sections
- Test changes: `ohmycode -p "Describe yourself" --mode auto`
- `OHMYCODE.md` is searched upward from current directory — put it at the repo root
