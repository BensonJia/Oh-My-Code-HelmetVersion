"""Three-layer configuration: defaults < user config < CLI overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "openai",
    "model": "gpt-4o",
    "llm": {
        "provider": "openai",
        "model": "gpt-4o",
        "base_url": "",
        "api_key": "",
        "auth_token": "",
        "azure_endpoint": "",
        "azure_api_version": "2024-02-01",
    },
    "mode": "default",
    "max_turns": 100,
    "token_budget": 200000,
    "output_tokens_reserved": 8192,
    "rules": [],
    "system_prompt_append": "",
    "search_api": "",
    "search_api_key": "",
    "azure_endpoint": "",
    "azure_api_version": "2024-02-01",
    "base_url": "",
    "api_key": "",
    "auth_token": "",
    "sandbox": {
        "enabled": False,
        "image": "python:3.11-slim",
        "workspace_root": "/workspace",
        "cpu_limit": "1.0",
        "memory_limit": "512m",
        "pids_limit": 256,
        "network_enabled": False,
    },
    "safety": {
        "enabled": True,
        "pause_on_severity": "medium",
        "sensitive_paths": [".env", ".ssh", "id_rsa", ".aws", ".npmrc"],
        "dangerous_commands": ["rm -rf", "mkfs", "shutdown", "reboot", "dd if=", ":(){", "chmod -R 777"],
        "llm_reviewer": {
            "enabled": False,
            "provider": "",
            "model": "",
            "base_url": "",
            "api_key": "",
            "auth_token": "",
            "azure_endpoint": "",
            "azure_api_version": "2024-02-01",
            "max_chars": 4000,
        },
    },
}


class SandboxSettings(BaseModel):
    enabled: bool = False
    image: str = "python:3.11-slim"
    workspace_root: str = "/workspace"
    cpu_limit: str = "1.0"
    memory_limit: str = "512m"
    pids_limit: int = 256
    network_enabled: bool = False


class LLMServiceSettings(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    base_url: str = ""
    api_key: str = ""
    auth_token: str = ""
    azure_endpoint: str = ""
    azure_api_version: str = "2024-02-01"


class LLMReviewerSettings(LLMServiceSettings):
    enabled: bool = False
    max_chars: int = 4000


class SafetyConfig(BaseModel):
    enabled: bool = True
    pause_on_severity: str = "medium"
    sensitive_paths: list[str] = Field(default_factory=lambda: [".env", ".ssh", "id_rsa", ".aws", ".npmrc"])
    dangerous_commands: list[str] = Field(default_factory=lambda: [
        "rm -rf",
        "mkfs",
        "shutdown",
        "reboot",
        "dd if=",
        ":(){",
        "chmod -R 777",
    ])
    llm_reviewer: LLMReviewerSettings = Field(default_factory=LLMReviewerSettings)


class OhMyCodeConfig(BaseModel):
    """Validated configuration object."""

    provider: str = "openai"
    model: str = "gpt-4o"
    llm: LLMServiceSettings = Field(default_factory=LLMServiceSettings)
    mode: str = "default"
    max_turns: int = 100
    token_budget: int = 200000
    output_tokens_reserved: int = 8192
    rules: list[dict[str, Any]] = Field(default_factory=list)
    system_prompt_append: str = ""
    search_api: str = ""
    search_api_key: str = ""
    azure_endpoint: str = ""
    azure_api_version: str = "2024-02-01"
    base_url: str = ""
    api_key: str = ""
    auth_token: str = ""
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)


def _sync_llm_settings(config_dict: dict[str, Any]) -> dict[str, Any]:
    result = dict(config_dict)

    llm = dict(result.get("llm") or {})
    for key in ("provider", "model", "base_url", "api_key", "auth_token", "azure_endpoint", "azure_api_version"):
        top_value = result.get(key)
        if top_value not in (None, ""):
            llm[key] = top_value
        elif llm.get(key) not in (None, ""):
            result[key] = llm[key]
    result["llm"] = llm

    safety = dict(result.get("safety") or {})
    reviewer = dict(safety.get("llm_reviewer") or {})
    reviewer_defaults = {
        "enabled": False,
        "provider": result.get("provider", "openai"),
        "model": "",
        "base_url": result.get("base_url", ""),
        "api_key": result.get("api_key", ""),
        "auth_token": result.get("auth_token", ""),
        "azure_endpoint": result.get("azure_endpoint", ""),
        "azure_api_version": result.get("azure_api_version", "2024-02-01"),
        "max_chars": 4000,
    }

    if "llm_reviewer_enabled" in safety:
        reviewer_defaults["enabled"] = bool(safety.get("llm_reviewer_enabled"))
    if safety.get("llm_reviewer_model"):
        reviewer_defaults["model"] = safety["llm_reviewer_model"]
    if safety.get("llm_reviewer_max_chars"):
        reviewer_defaults["max_chars"] = safety["llm_reviewer_max_chars"]

    reviewer_defaults.update({k: v for k, v in reviewer.items() if v is not None})
    for key in ("provider", "base_url", "api_key", "auth_token", "azure_endpoint", "azure_api_version"):
        if reviewer_defaults.get(key) in (None, ""):
            reviewer_defaults[key] = result.get(key, "")
    safety["llm_reviewer"] = reviewer_defaults
    result["safety"] = safety
    return result


def _normalize_config_layer(layer: dict[str, Any]) -> dict[str, Any]:
    result = dict(layer)
    llm = dict(result.get("llm") or {})
    for key in ("provider", "model", "base_url", "api_key", "auth_token", "azure_endpoint", "azure_api_version"):
        if key not in result and llm.get(key) not in (None, ""):
            result[key] = llm[key]
    return result


def _strip_cli_llm_overrides(cli_overrides: dict[str, Any]) -> dict[str, Any]:
    result = dict(cli_overrides)
    for key in (
        "provider",
        "model",
        "base_url",
        "api_key",
        "auth_token",
        "azure_endpoint",
        "azure_api_version",
        "llm",
    ):
        result.pop(key, None)

    safety = result.get("safety")
    if isinstance(safety, dict):
        safety = dict(safety)
        safety.pop("llm_reviewer", None)
        result["safety"] = safety
    return result


def merge_configs(base: dict, override: dict) -> dict:
    """Merge two config dicts: scalars override, lists concatenate, dicts merge deeply."""
    result = dict(base)
    for key, value in override.items():
        if key not in result:
            result[key] = value
        elif isinstance(value, list) and isinstance(result[key], list):
            result[key] = result[key] + value
        elif isinstance(value, dict) and isinstance(result[key], dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def _read_json(path: Path) -> dict:
    """Read a JSON config file; return an empty dict if missing or invalid."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_config(cli_overrides: dict[str, Any]) -> OhMyCodeConfig:
    """Load configuration from three layers: defaults < user config < CLI."""
    home = Path(os.environ.get("HOME", Path.home()))
    user_config = _normalize_config_layer(_read_json(home / ".ohmycode" / "config.json"))

    cli_clean = _strip_cli_llm_overrides({
        k: v for k, v in cli_overrides.items() if v is not None
    })

    merged = DEFAULT_CONFIG.copy()
    merged = merge_configs(merged, user_config)
    merged = merge_configs(merged, cli_clean)
    merged = _sync_llm_settings(merged)

    return OhMyCodeConfig(**merged)
