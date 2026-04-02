# OhMyCode 参数配置说明

本文档说明当前项目可用的主要接口参数与配置项，包含：

- 配置文件参数
- CLI 启动参数
- `sandbox` 容器隔离参数
- `safety` 安全预警参数

## 配置加载优先级

配置按以下顺序覆盖，越靠后优先级越高：

```text
默认值 < ~/.ohmycode/config.json < CLI 参数
```

## 顶层配置项

配置定义见 [config.py](/c:/Users/BohuiJia/Documents/Projects/DataAgent/OhMyCode-main/ohmycode/config/config.py)。

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `provider` | `str` | `"openai"` | 使用的模型提供方 |
| `model` | `str` | `"gpt-4o"` | 模型名称 |
| `mode` | `str` | `"default"` | 运行模式，可选 `default` / `auto` / `plan` |
| `max_turns` | `int` | `100` | 单次任务内最大回合数 |
| `token_budget` | `int` | `200000` | 总上下文 token 预算 |
| `output_tokens_reserved` | `int` | `8192` | 预留给模型输出的 token 数 |
| `rules` | `list[dict]` | `[]` | 权限规则列表 |
| `system_prompt_append` | `str` | `""` | 追加到 system prompt 的自定义内容 |
| `search_api` | `str` | `""` | 搜索服务名称或标识 |
| `search_api_key` | `str` | `""` | 搜索服务密钥 |
| `azure_endpoint` | `str` | `""` | Azure OpenAI endpoint |
| `azure_api_version` | `str` | `"2024-02-01"` | Azure OpenAI API 版本 |
| `base_url` | `str` | `""` | 自定义 provider base URL |
| `api_key` | `str` | `""` | provider API key |
| `auth_token` | `str` | `""` | 额外认证 token，当前主要用于部分 provider |
| `sandbox` | `object` | 见下文 | 容器隔离配置 |
| `safety` | `object` | 见下文 | 安全预警配置 |

## `rules` 权限规则

每条规则格式如下：

```json
{
  "tool": "bash",
  "match_field": "command",
  "pattern": "rm*",
  "match_type": "glob",
  "action": "deny"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tool` | `str` | 是 | 工具名，如 `bash`、`write` |
| `match_field` | `str` | 否 | 要匹配的参数字段 |
| `pattern` | `str` | 否 | 匹配模式 |
| `match_type` | `str` | 否 | `glob` 或 `regex`，默认 `glob` |
| `action` | `str` | 否 | `allow` / `deny` / `ask`，默认 `ask` |

## `sandbox` 容器参数

`sandbox` 用于控制 Docker 隔离执行。

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `sandbox.enabled` | `bool` | `false` | 是否启用 Docker 沙箱 |
| `sandbox.image` | `str` | `"python:3.11-slim"` | Docker 镜像名 |
| `sandbox.workspace_root` | `str` | `"/workspace"` | 容器内工作区根路径 |
| `sandbox.cpu_limit` | `str` | `"1.0"` | Docker `--cpus` 限制 |
| `sandbox.memory_limit` | `str` | `"512m"` | Docker `--memory` 限制 |
| `sandbox.pids_limit` | `int` | `256` | Docker `--pids-limit` 限制 |
| `sandbox.network_enabled` | `bool` | `false` | 是否允许容器联网；`false` 时使用 `--network none` |

行为说明：

- 启用后，`bash/read/write/edit/glob/grep` 会通过 Docker runtime 执行。
- Agent 看到的工作区根路径是 `sandbox.workspace_root`，默认 `/workspace`。
- 访问工作区外路径会被 runtime 拒绝。

## `safety` 安全预警参数

`safety` 用于控制工具执行前的风险检查。

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `safety.enabled` | `bool` | `true` | 是否启用安全预警 |
| `safety.pause_on_severity` | `str` | `"medium"` | 达到该严重级别时暂停执行，当前支持 `low` / `medium` / `high` / `critical` |
| `safety.sensitive_paths` | `list[str]` | `[".env", ".ssh", "id_rsa", ".aws", ".npmrc"]` | 识别敏感路径的关键字 |
| `safety.dangerous_commands` | `list[str]` | `["rm -rf", "mkfs", "shutdown", "reboot", "dd if=", ":(){", "chmod -R 777"]` | 识别高风险 shell 命令的模式列表 |

行为说明：

- 工具先通过权限检查，再进入 `SafetyEngine`。
- 命中风险后，CLI 会展示 `SafetyAlert`，等待用户放行。
- 用户可以选择：
  - `y`: 本次允许
  - `n`: 本次拒绝
  - `a`: 本会话对该工具后续自动允许

## CLI 参数

CLI 参数定义见 [cli.py](/c:/Users/BohuiJia/Documents/Projects/DataAgent/OhMyCode-main/ohmycode/cli.py)。

| 参数 | 说明 |
|---|---|
| `-p`, `--prompt` | 单次 prompt 模式，执行完退出 |
| `--provider` | 覆盖 `provider` |
| `--model` | 覆盖 `model` |
| `--mode` | 覆盖 `mode` |
| `--api-key` | 覆盖 `api_key` |
| `--base-url` | 覆盖 `base_url` |
| `--resume [ID]` | 恢复历史会话；不带值时恢复最近一次 |

另外支持子命令：

| 子命令 | 说明 |
|---|---|
| `ohmycode vchange` | 查看最近版本位置 |
| `ohmycode vchange -1` | 切到上一个 commit |
| `ohmycode vchange 1` | 切到下一个 commit |

## 推荐配置示例

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

## 当前实现注意点

- `sandbox` 配置已经接入运行时，但只有在 `sandbox.enabled=true` 时才会切到 Docker 执行。
- `safety` 当前是确定性规则引擎，不依赖额外 LLM。
- `search_api` 和 `search_api_key` 目前只是保留在配置模型里，是否实际生效取决于对应搜索工具实现。
