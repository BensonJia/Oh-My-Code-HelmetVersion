<div align="center">
  <h1 style="display: flex; align-items: center; justify-content: center; gap: 14px; flex-wrap: wrap; margin: 0.5em 0; line-height: 0;">
    <img src="assets/octopus_helmet.png" alt="" width="100" height="100" style="display: block; align-self: center;">
    <img src="assets/HelmetVersion.png" alt="OhMyCode" height="90" style="display: block; width: auto; align-self: center;">
  </h1>
  <p><b>Modified version of OhMyCode, a CC-Style Coding Agent with Sandbox and security check, code safer. </b></p>
  <blockquote><i>
    A fully-functional CC-style AI coding assistant you can read in an afternoon — and tell it to extend itself.<br>
    <span style="color:#ec407a;font-style:italic;">"Oh My Code!!!"</span>
  </i></blockquote>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.9-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/lines-~3000-orange" alt="Lines">
    <img src="https://img.shields.io/badge/tools-9-cyan" alt="Tools">
    <img src="https://img.shields.io/badge/tests-214-brightgreen" alt="Tests">
  </p>
</div>

Special Thanks to [OhMyCode](https://github.com/AlphaLab-USTC/OhMyCode), for your nice claude-code like agent framework❤.

## Why OhMyCode with a 🪖Helmet?

🤏 **It's tiny.** OhMyCode delivers the CC-style coding assistant experience — streaming, tool use, context compression, memory — in ~3000 lines you fully own.

🧬 **OhMyCode extends itself.** Tell **OhMyCode** to "add a tool that does X" and it edits *this* repo's source to build one — no plugin SDK, no API boundaries between you and the code.

🪖 **Sandbox + rule/LLM-driven censor** Run all command in your sandbox, keep your computer tidy and safe.

<div align="center">
  <img src="assets/entry.png" alt="OhMyCode Main Entry" width="600">
</div>

## Highlights

- 🧩 **Minimal CC Core** — Streaming output, tool execution, permission modes, context compression, memory, and resume in ~3000 lines.
- 🔧 **Deeply Customizable** — Add your own tools/providers/prompts or just ask OhMyCode to extend itself by editing its own source.
- 🎒 **Skills Included** — Comes with practical built-in skills for add-tool, add-provider, add-feature, debugging, workflow conventions, test generation, and benchmarking.
- 🌐 **Provider Flexibility** — Works with OpenAI, Anthropic, Azure, and OpenAI-compatible APIs.
- 🪖 **Rule + LLM Safety Guardrails** — Helmet version combines fast rule-based checks with an LLM safety reviewer to catch suspicious commands, secret access, destructive actions, and potential exfiltration. Need a deeper read before approving? Invoke **Helmet** for on-demand risk identification and a plain-language summary of what the action is likely to do.

## Install

```bash
git clone <repo-url>
cd OhMyCode
./scripts/setup-cli.sh
```

> [!TIP]
> This project is CLI-first. Start it with `ohmycode` command only.
> If command is still not found after setup, reload shell and verify:
> `source ~/.zshrc && which ohmycode`
>
> `./scripts/setup-cli.sh` installs a stable global shim at `~/.local/bin/ohmycode`,
> so it works consistently across different shell sessions and conda environments.

## Quick Start

```bash
ohmycode                        # interactive REPL
ohmycode -p "Fix the bug"      # single-shot prompt
ohmycode --resume               # resume last conversation
ohmycode --mode plan            # read-only mode
```

Verify CLI wiring (recommended for agents and CI scripts):

```bash
pip3 show ohmycode | rg "Editable project location|Location"
which ohmycode
ohmycode --help
```

## Safety and Sandbox

OhMyCode separates **permissions**, **pre-execution safety review**, and **runtime isolation**:

- **Permissions** decide whether a tool call is allowed, denied, or requires confirmation.
- **Safety review** runs before execution and can pause risky actions with an explanation. When enabled, a lightweight LLM reviewer can escalate suspicious context.
- **Helmet** is the on-demand deep reviewer in confirmation prompts. It summarizes likely impact before you decide whether to continue.
- **Sandbox runtime** keeps command and file tools inside the workspace boundary. With sandboxing enabled, these tools can run in a Docker-backed environment instead of directly on the host.

### REPL Commands

| Command | Description |
|---------|------------|
| `/exit` | Quit (auto-saves + extracts memories) |
| `/clear` | Clear history |
| `/mode <mode>` | Switch mode (`default` / `auto` / `plan`) |
| `/memory list\|delete` | Manage memories |
| `/skills` | List skills |
| `/<skill-name>` | Run a skill |

## Configuration

Create `~/.ohmycode/config.json`:

```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "api_key": "sk-...",
  "mode": "auto"
}
```

Config merges four layers: **system defaults** < **user** (`~/.ohmycode/`) < **project** (`.ohmycode/`) < **CLI args**.

CLI overrides: `--provider`, `--model`, `--mode`, `--api-key`, `--base-url`.

<details>
<summary>All config options</summary>

| Key | Default | Description |
|-----|---------|-------------|
| `provider` | `"openai"` | LLM provider |
| `model` | `"gpt-4o"` | Model name |
| `mode` | `"default"` | Permission mode |
| `base_url` | `""` | API base URL |
| `api_key` | `""` | API key |
| `azure_endpoint` | `""` | Azure endpoint |
| `azure_api_version` | `"2024-02-01"` | Azure API version |
| `max_turns` | `100` | Max conversation turns |
| `token_budget` | `200000` | Token budget |
| `output_tokens_reserved` | `8192` | Reserved output tokens |
| `rules` | `[]` | Permission rules |
| `system_prompt_append` | `""` | Appended to system prompt |
| `search_api` / `search_api_key` | `""` | Web search API config |
| `sandbox.*` | see defaults | Docker-backed workspace sandbox settings |
| `safety.*` | see defaults | Pre-execution safety review and Helmet reviewer settings |

</details>

Example with sandbox and safety review enabled:

```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "api_key": "sk-...",
  "mode": "auto",
  "sandbox": {
    "enabled": true,
    "image": "python:3.11-slim",
    "network_enabled": false
  },
  "safety": {
    "enabled": true,
    "pause_on_severity": "medium",
    "llm_reviewer": {
      "enabled": true,
      "model": "gpt-4o-mini"
    }
  }
}
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `bash` | Shell commands with timeout |
| `read` | Read files with line range |
| `edit` | Find-and-replace (unique match) |
| `write` | Create/overwrite files |
| `glob` | Find files by pattern |
| `grep` | Regex search across files |
| `web_fetch` | Fetch URL → text |
| `web_search` | DuckDuckGo search |
| `agent` | Sub-agent (max depth 2) |

## Extending (or: Let It Extend Itself)

The fastest way to add a feature? **Ask OhMyCode to do it.** It can read its own source, write new files, and run tests — so "add a tool that counts words" is a single prompt away.

You can also do it manually:

- **Add a tool** — create `ohmycode/tools/my_tool.py`, auto-discovered. See `/add-tool` skill.
- **Add a provider** — create `ohmycode/providers/my_provider.py`, auto-discovered. See `/add-provider` skill.
- **Add a skill** — create `SKILL.md` in `.ohmycode/skills/`, `.claude/skills/`, `.agents/skills/`, or `~/.ohmycode/skills/` (searched in that order).

## Testing

```bash
python3 -m pytest tests/ -v          # 190 unit tests
```

### Benchmarking

OhMyCode ships with a built-in benchmark suite — 8 SWE-bench-style coding tasks that test code generation, bug fixing, refactoring, test generation, tool use, and code comprehension.

```bash
python3 benchmarks/run_bench.py                        # full benchmark, current config
python3 benchmarks/run_bench.py --model gpt-4o-mini    # compare a different model
python3 benchmarks/run_bench.py --dry-run              # validate tasks without LLM
```

Or from the REPL: `/bench`

The harness tracks **token usage (in/out)** per task and outputs a scorecard + `bench_results.json` for model comparison.

### Development Closed-Loop

OhMyCode includes skills for a TDD-style development loop:

```
code  →  /gen-tests  →  /run-tests  →  fix  →  repeat
```

| Skill | Purpose |
|-------|---------|
| `/gen-tests <module>` | Generate tests following project conventions |
| `/run-tests [scope]` | Run tests, analyze failures, fix, re-run |
| `/bench` | Score any provider/model with 8 agent tasks |

## License

MIT
