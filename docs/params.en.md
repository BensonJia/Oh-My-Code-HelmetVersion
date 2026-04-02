# OhMyCode Parameter Reference

This document describes the main runtime and configuration parameters currently supported by the project, including:

- config file parameters
- CLI startup parameters
- `sandbox` container isolation parameters
- `safety` pre-execution warning parameters

## Configuration Precedence

Configuration is merged in this order, with later sources taking precedence:

```text
defaults < ~/.ohmycode/config.json < CLI session arguments
```

LLM service settings are config-only. The CLI does not override `provider`, `model`, `api_key`, `base_url`, or nested `llm` settings.

## Top-Level Configuration Fields

The source of truth is [config.py](/config/config.py).

| Parameter | Type | Default | Description |
|---|---|---:|---|
| `provider` | `str` | `"openai"` | Effective LLM provider name, normally sourced from `llm.provider` |
| `model` | `str` | `"gpt-4o"` | Effective model name, normally sourced from `llm.model` |
| `mode` | `str` | `"default"` | Runtime mode: `default`, `auto`, or `plan` |
| `max_turns` | `int` | `100` | Maximum loop iterations for one task |
| `token_budget` | `int` | `200000` | Total context token budget |
| `output_tokens_reserved` | `int` | `8192` | Tokens reserved for model output |
| `rules` | `list[dict]` | `[]` | Permission rule list |
| `system_prompt_append` | `str` | `""` | Extra content appended to the system prompt |
| `search_api` | `str` | `""` | Search provider identifier |
| `search_api_key` | `str` | `""` | Search provider API key |
| `azure_endpoint` | `str` | `""` | Azure OpenAI endpoint |
| `azure_api_version` | `str` | `"2024-02-01"` | Azure OpenAI API version |
| `base_url` | `str` | `""` | Custom provider base URL |
| `api_key` | `str` | `""` | Provider API key |
| `auth_token` | `str` | `""` | Extra auth token used by some providers |
| `sandbox` | `object` | see below | Container isolation settings |
| `safety` | `object` | see below | Pre-execution safety review settings |

Recommended service layout:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-key"
  },
  "safety": {
    "llm_reviewer": {
      "enabled": true,
      "model": "gpt-4o-mini"
    }
  }
}
```

## `rules` Permission Rules

Each rule uses this shape:

```json
{
  "tool": "bash",
  "match_field": "command",
  "pattern": "rm*",
  "match_type": "glob",
  "action": "deny"
}
```

Field reference:

| Field | Type | Required | Description |
|---|---|---|---|
| `tool` | `str` | yes | Tool name, such as `bash` or `write` |
| `match_field` | `str` | no | Parameter field to inspect |
| `pattern` | `str` | no | Match pattern |
| `match_type` | `str` | no | `glob` or `regex`, default is `glob` |
| `action` | `str` | no | `allow`, `deny`, or `ask`, default is `ask` |

## `sandbox` Container Parameters

`sandbox` controls Docker-backed isolated execution.

| Parameter | Type | Default | Description |
|---|---|---:|---|
| `sandbox.enabled` | `bool` | `false` | Enables Docker sandbox execution |
| `sandbox.image` | `str` | `"python:3.11-slim"` | Docker image name |
| `sandbox.workspace_root` | `str` | `"/workspace"` | Visible workspace root inside the container |
| `sandbox.cpu_limit` | `str` | `"1.0"` | Docker `--cpus` limit |
| `sandbox.memory_limit` | `str` | `"512m"` | Docker `--memory` limit |
| `sandbox.pids_limit` | `int` | `256` | Docker `--pids-limit` value |
| `sandbox.network_enabled` | `bool` | `false` | Whether container networking is allowed; `false` maps to `--network none` |

Behavior notes:

- When enabled, `bash`, `read`, `write`, `edit`, `glob`, and `grep` run through the Docker runtime.
- The agent sees the workspace root as `sandbox.workspace_root`, which defaults to `/workspace`.
- Access to paths outside the workspace is rejected by the runtime.
- In REPL mode, sandbox execution uses one persistent container for the whole session.
- On exit, the operator can export the current sandbox to `~/.ohmycode/sandboxes/<conversation-id>.tar`.
- When resuming a saved conversation with `--resume`, OhMyCode asks whether to restore the matching sandbox snapshot before creating a fresh one from config.

## `safety` Warning Parameters

`safety` controls pre-execution risk review.

| Parameter | Type | Default | Description |
|---|---|---:|---|
| `safety.enabled` | `bool` | `true` | Enables safety review |
| `safety.pause_on_severity` | `str` | `"medium"` | Pause execution at or above this severity; supported values are `low`, `medium`, `high`, `critical` |
| `safety.sensitive_paths` | `list[str]` | `[".env", ".ssh", "id_rsa", ".aws", ".npmrc"]` | Path markers treated as sensitive |
| `safety.dangerous_commands` | `list[str]` | `["rm -rf", "mkfs", "shutdown", "reboot", "dd if=", ":(){", "chmod -R 777"]` | Command patterns treated as dangerous |

Behavior notes:

- Tools go through permission checks first, then `SafetyEngine`.
- If a risky call is detected, the CLI shows a `SafetyAlert` and waits for approval.
- The operator can choose:
  - `y`: allow once
  - `n`: deny once
  - `a`: auto-approve future calls for that tool in the current session

## CLI Parameters

The CLI definition lives in [cli.py](/c:/Users/BohuiJia/Documents/Projects/DataAgent/OhMyCode-main/ohmycode/cli.py).

| Parameter | Description |
|---|---|
| `-p`, `--prompt` | Run a single prompt and exit |
| `--mode` | Override `mode` |
| `--resume [ID]` | Resume a saved conversation; without a value, resumes the latest one |

Supported subcommands:

| Subcommand | Description |
|---|---|
| `ohmycode vchange` | Show recent version position |
| `ohmycode vchange -1` | Move to the previous commit |
| `ohmycode vchange 1` | Move to the next commit |

## Recommended Example

```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "mode": "default",
  "max_turns": 100,
  "token_budget": 200000,
  "output_tokens_reserved": 8192,
  "sandbox": {
    "enabled": true,
    "image": "python:3.11-slim",
    "workspace_root": "/workspace",
    "cpu_limit": "1.0",
    "memory_limit": "512m",
    "pids_limit": 256,
    "network_enabled": false
  },
  "safety": {
    "enabled": true,
    "pause_on_severity": "medium",
    "sensitive_paths": [".env", ".ssh", "id_rsa", ".aws", ".npmrc"],
    "dangerous_commands": ["rm -rf", "mkfs", "shutdown", "reboot", "dd if=", ":(){", "chmod -R 777"]
  },
  "rules": [
    {
      "tool": "bash",
      "match_field": "command",
      "pattern": "docker * --privileged*",
      "match_type": "glob",
      "action": "deny"
    }
  ]
}
```

## Current Implementation Notes

- `sandbox` is wired into the runtime layer, but Docker execution is only enabled when `sandbox.enabled=true`.
- `safety` is currently deterministic and rule-based; it does not require an extra LLM.
- `search_api` and `search_api_key` are present in the config model, but whether they are used depends on the corresponding search tool implementation.
