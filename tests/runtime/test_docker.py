from __future__ import annotations

from pathlib import Path

import pytest

from ohmycode.runtime.base import RuntimeCommandResult, RuntimeLimits, SandboxConfig
from ohmycode.runtime.docker import DockerSandboxRuntime


class FakeDockerRunner:
    def __init__(self):
        self.calls: list[dict] = []

    async def __call__(self, args, cwd=None, timeout=None, input_text=None):
        self.calls.append(
            {
                "args": list(args),
                "cwd": cwd,
                "timeout": timeout,
                "input_text": input_text,
            }
        )
        return RuntimeCommandResult(stdout="ok", stderr="", exit_code=0)


@pytest.mark.asyncio
async def test_exec_uses_docker_workspace_mount(tmp_path: Path):
    runner = FakeDockerRunner()
    runtime = DockerSandboxRuntime(
        host_workspace=tmp_path,
        sandbox=SandboxConfig(enabled=True),
        limits=RuntimeLimits(cpu_limit="1.0", memory_limit="256m", pids_limit=64),
        command_runner=runner,
    )

    result = await runtime.exec("pwd", timeout=9)

    assert not result.is_error
    args = runner.calls[0]["args"]
    assert args[:2] == ["docker", "run"]
    assert "--rm" in args
    assert "--network" in args
    assert "/workspace" in " ".join(args)
    assert str(tmp_path) in " ".join(args)


@pytest.mark.asyncio
async def test_read_maps_host_path_into_workspace(tmp_path: Path):
    runner = FakeDockerRunner()
    host_file = tmp_path / "src" / "app.py"
    runtime = DockerSandboxRuntime(
        host_workspace=tmp_path,
        sandbox=SandboxConfig(enabled=True),
        limits=RuntimeLimits(),
        command_runner=runner,
    )

    await runtime.read_file(host_file)

    args = runner.calls[0]["args"]
    joined = " ".join(args)
    assert "/workspace/src/app.py" in joined
    assert str(host_file) not in joined


@pytest.mark.asyncio
async def test_read_accepts_container_workspace_path(tmp_path: Path):
    runner = FakeDockerRunner()
    runtime = DockerSandboxRuntime(
        host_workspace=tmp_path,
        sandbox=SandboxConfig(enabled=True),
        limits=RuntimeLimits(),
        command_runner=runner,
    )

    await runtime.read_file("/workspace/pyproject.toml")

    args = runner.calls[0]["args"]
    joined = " ".join(args)
    assert "/workspace/pyproject.toml" in joined
