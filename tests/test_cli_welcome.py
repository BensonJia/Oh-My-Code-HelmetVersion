"""Tests for REPL welcome text metadata."""

from types import SimpleNamespace

from ohmycode.cli import _build_repl_welcome_text, _build_sandbox_status
from ohmycode.config.config import OhMyCodeConfig


def test_build_sandbox_status_returns_not_available_when_disabled():
    config = OhMyCodeConfig()
    assert _build_sandbox_status(config, None, docker_available=True) == "not available"


def test_build_sandbox_status_returns_not_available_when_docker_missing():
    config = OhMyCodeConfig(sandbox={"enabled": True, "image": "python:3.11-slim"})
    assert _build_sandbox_status(config, None, docker_available=False) == "not available"


def test_build_sandbox_status_includes_loaded_container_config():
    config = OhMyCodeConfig(sandbox={
        "enabled": True,
        "image": "python:3.11-slim",
        "cpu_limit": "8.0",
        "memory_limit": "8192m",
        "network_enabled": True,
    })
    runtime = SimpleNamespace(container_name="omc-demo", sandbox=config.sandbox)

    status = _build_sandbox_status(config, runtime, docker_available=True)

    assert "omc-demo" in status
    assert "python:3.11-slim" in status
    assert "cpu=8.0" in status
    assert "mem=8192m" in status
    assert "net=on" in status


def test_build_repl_welcome_text_includes_sandbox_line():
    text = _build_repl_welcome_text(
        model_display="gpt-4o",
        mode="default",
        n_skills=24,
        sandbox_status="omc-demo | python:3.11-slim | cpu=8.0 | mem=8192m | net=on",
    )

    rendered = text.plain
    assert "Sandbox" in rendered
    assert "omc-demo | python:3.11-slim" in rendered
    assert "helmet version 0.1.0" in rendered


def test_build_repl_welcome_text_uses_helmet_branding():
    text = _build_repl_welcome_text(
        model_display="gpt-4o",
        mode="default",
        n_skills=24,
        sandbox_status="not available",
    )

    rendered = text.plain
    assert "helmet version 0.1.0" in rendered
