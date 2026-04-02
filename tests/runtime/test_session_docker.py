from __future__ import annotations

from pathlib import Path

import pytest

from ohmycode.runtime.base import RuntimeCommandResult, RuntimeLimits, SandboxConfig
from ohmycode.runtime.docker import SessionDockerRuntime


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
async def test_session_runtime_starts_named_container_and_uses_exec(tmp_path: Path):
    runner = FakeDockerRunner()
    runtime = SessionDockerRuntime(
        host_workspace=tmp_path,
        sandbox=SandboxConfig(enabled=True),
        limits=RuntimeLimits(cpu_limit="1.0", memory_limit="256m", pids_limit=64),
        session_name="session-123",
        command_runner=runner,
    )

    await runtime.start()
    await runtime.exec("pwd", timeout=9)

    start_args = runner.calls[0]["args"]
    exec_args = runner.calls[1]["args"]

    assert start_args[:3] == ["docker", "run", "-d"]
    assert "--name" in start_args
    assert "omc-session-123" in start_args
    assert "--rm" not in start_args
    assert exec_args[:3] == ["docker", "exec", "omc-session-123"]
    assert exec_args[-3:] == ["sh", "-lc", "pwd"]


@pytest.mark.asyncio
async def test_session_runtime_snapshot_commits_and_saves_image(tmp_path: Path):
    runner = FakeDockerRunner()
    runtime = SessionDockerRuntime(
        host_workspace=tmp_path,
        sandbox=SandboxConfig(enabled=True),
        limits=RuntimeLimits(),
        session_name="session-123",
        command_runner=runner,
    )

    archive_path = tmp_path / "snapshots" / "session-123.tar"
    image_ref = await runtime.save_snapshot(archive_path)

    commit_args = runner.calls[0]["args"]
    save_args = runner.calls[1]["args"]

    assert image_ref.startswith("ohmycode-sandbox:session-123-")
    assert commit_args[:3] == ["docker", "commit", "omc-session-123"]
    assert save_args[:3] == ["docker", "save", "-o"]
    assert str(archive_path) in save_args
    assert image_ref in save_args
