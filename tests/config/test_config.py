"""Tests for four-layer configuration merging."""

import json
from pathlib import Path

from ohmycode.config.config import DEFAULT_CONFIG, OhMyCodeConfig, load_config, merge_configs


def test_default_config_has_required_keys():
    assert "provider" in DEFAULT_CONFIG
    assert "model" in DEFAULT_CONFIG
    assert "mode" in DEFAULT_CONFIG
    assert "max_turns" in DEFAULT_CONFIG
    assert "rules" in DEFAULT_CONFIG


def test_merge_scalar_override():
    base = {"provider": "anthropic", "model": "claude-3"}
    override = {"model": "gpt-4o"}
    result = merge_configs(base, override)
    assert result["provider"] == "anthropic"
    assert result["model"] == "gpt-4o"


def test_merge_array_concat():
    base = {"rules": [{"tool": "bash", "action": "deny"}]}
    override = {"rules": [{"tool": "edit", "action": "ask"}]}
    result = merge_configs(base, override)
    assert len(result["rules"]) == 2


def test_merge_deep_object():
    base = {"a": {"b": 1, "c": 2}}
    override = {"a": {"c": 3, "d": 4}}
    result = merge_configs(base, override)
    assert result["a"] == {"b": 1, "c": 3, "d": 4}


def test_load_config_defaults_only(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    config = load_config(cli_overrides={})
    assert config.provider == DEFAULT_CONFIG["provider"]
    assert config.mode == "default"


def test_load_config_user_override(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / ".ohmycode"
    user_dir.mkdir()
    (user_dir / "config.json").write_text(json.dumps({"model": "gpt-4o-mini"}))
    config = load_config(cli_overrides={})
    assert config.model == "gpt-4o-mini"


def test_load_config_cli_mode_wins(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / ".ohmycode"
    user_dir.mkdir()
    (user_dir / "config.json").write_text(json.dumps({"mode": "default"}))
    config = load_config(cli_overrides={"mode": "auto"})
    assert config.mode == "auto"


def test_load_config_ignores_cli_llm_overrides(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / ".ohmycode"
    user_dir.mkdir()
    (user_dir / "config.json").write_text(json.dumps({
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "config-key",
            "base_url": "https://example.invalid/v1",
        }
    }))
    config = load_config(cli_overrides={
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-latest",
        "api_key": "cli-key",
        "base_url": "https://override.invalid/v1",
        "llm": {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-latest",
            "api_key": "cli-key",
        },
    })
    assert config.provider == "openai"
    assert config.model == "gpt-4o-mini"
    assert config.api_key == "config-key"
    assert config.base_url == "https://example.invalid/v1"


def test_ohmycode_config_validation():
    config = OhMyCodeConfig(**DEFAULT_CONFIG)
    assert config.max_turns == 100
    assert config.output_tokens_reserved == 8192


def test_load_config_supports_nested_llm_block(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / ".ohmycode"
    user_dir.mkdir()
    (user_dir / "config.json").write_text(json.dumps({
        "llm": {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-latest",
            "api_key": "nested-key",
            "base_url": "https://example.invalid",
        }
    }))
    config = load_config(cli_overrides={})
    assert config.provider == "anthropic"
    assert config.model == "claude-3-5-sonnet-latest"
    assert config.api_key == "nested-key"
    assert config.base_url == "https://example.invalid"


def test_load_config_supports_reviewer_specific_model(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / ".ohmycode"
    user_dir.mkdir()
    (user_dir / "config.json").write_text(json.dumps({
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "main-key",
        },
        "safety": {
            "llm_reviewer": {
                "enabled": True,
                "model": "gpt-4o-mini"
            }
        }
    }))
    config = load_config(cli_overrides={})
    assert config.safety.llm_reviewer.enabled is True
    assert config.safety.llm_reviewer.model == "gpt-4o-mini"
    assert config.safety.llm_reviewer.provider == "openai"
    assert config.safety.llm_reviewer.api_key == "main-key"


def test_load_config_ignores_project_level_config_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home_dir = tmp_path / "home" / ".ohmycode"
    home_dir.mkdir(parents=True)
    project_dir = tmp_path / "project" / ".ohmycode"
    project_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "project")

    (home_dir / "config.json").write_text(json.dumps({"model": "gpt-4o-mini"}))
    (project_dir / "config.json").write_text(json.dumps({"model": "claude-3-5-sonnet-latest"}))

    config = load_config(cli_overrides={})

    assert config.model == "gpt-4o-mini"
