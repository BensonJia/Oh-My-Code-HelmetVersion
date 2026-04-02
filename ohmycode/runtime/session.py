"""Session-scoped sandbox helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ohmycode.runtime.base import SandboxConfig
from ohmycode.runtime.docker import SessionDockerRuntime


def _sandbox_to_dict(sandbox: Any) -> dict[str, Any]:
    if hasattr(sandbox, "model_dump"):
        return sandbox.model_dump()
    if hasattr(sandbox, "dict"):
        return sandbox.dict()
    return dict(sandbox)


def build_sandbox_config(config_like: Any) -> SandboxConfig:
    return SandboxConfig(**_sandbox_to_dict(config_like))


async def create_session_runtime(
    host_workspace: Path,
    sandbox: SandboxConfig,
    session_name: str,
    snapshot: dict[str, Any] | None = None,
) -> SessionDockerRuntime:
    sandbox_cfg = SandboxConfig(**(snapshot.get("sandbox_config") or _sandbox_to_dict(sandbox))) if snapshot else sandbox
    image = snapshot.get("image_ref") if snapshot else None
    runtime = SessionDockerRuntime(
        host_workspace=host_workspace,
        sandbox=sandbox_cfg,
        limits=sandbox_cfg.to_runtime_limits(),
        session_name=session_name,
        image=image,
    )
    if snapshot:
        await runtime.load_snapshot(Path(snapshot["archive_path"]))
    start_result = await runtime.start()
    if start_result.is_error:
        raise RuntimeError(start_result.output)
    return runtime
