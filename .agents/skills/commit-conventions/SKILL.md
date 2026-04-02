---
name: commit-conventions
description: OhMyCode commit message conventions. MUST load on every git commit — provides Conventional Commits format with scope inference from file paths.
---

# OhMyCode Commit Conventions

## Format

```
<type>(<scope>): <description>
```

**All lowercase.** Description should be imperative mood ("add", not "adds" or "added").

## Types

| Type | When to Use |
|------|------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `chore` | Build, tooling, dependency changes |
| `style` | Formatting, whitespace (no logic change) |

## Scope Inference

Infer scope from the primary file path changed:

| Path Pattern | Scope |
|-------------|-------|
| `ohmycode/tools/*` | `tools` |
| `ohmycode/core/*` | `core` |
| `ohmycode/providers/*` | `providers` |
| `ohmycode/config/*` | `config` |
| `ohmycode/memory/*` | `memory` |
| `ohmycode/storage/*` | `storage` |
| `ohmycode/cli.py` | `cli` |
| `tests/*` | same as the source being tested |
| `docs/*` | omit scope |
| `.claude/skills/*` or `.agents/skills/*` | `skills` |

If changes span multiple scopes, use the primary one or omit scope.

## Examples

```
feat(tools): add sql_query tool
fix(providers): handle empty delta in OpenAI streaming
docs: update DEVELOPMENT_GUIDE with hook system
test(core): add permission rule matching edge cases
refactor(cli): extract render_stream into separate module
chore: bump openai dependency to 1.52.0
feat(skills): add debug-ohmycode skill
```

## Rules

- First line under 72 characters
- No period at the end
- Body is optional — add if the change needs explanation
- Reference issue numbers if applicable: `fix(core): handle empty messages (#42)`
- Breaking changes: add `!` after scope: `feat(config)!: change rules format`
