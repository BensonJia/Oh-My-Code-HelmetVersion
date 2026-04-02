from __future__ import annotations

from ohmycode.config.config import OhMyCodeConfig
from ohmycode.runtime.base import RuntimeLimits, SandboxConfig


def test_config_exposes_sandbox_settings():
    config = OhMyCodeConfig()
    assert config.sandbox.enabled is False
    assert config.sandbox.image
    assert config.sandbox.workspace_root == "/workspace"


def test_sandbox_config_builds_limits():
    sandbox = SandboxConfig(
        enabled=True,
        image="python:3.11-slim",
        workspace_root="/workspace",
        cpu_limit="1.5",
        memory_limit="512m",
        pids_limit=128,
        network_enabled=False,
    )
    limits = sandbox.to_runtime_limits()
    assert limits == RuntimeLimits(cpu_limit="1.5", memory_limit="512m", pids_limit=128)
