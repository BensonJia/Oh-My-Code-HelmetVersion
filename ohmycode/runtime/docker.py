"""Docker-backed runtime for sandboxed execution."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from pathlib import Path
from textwrap import dedent

from .base import BaseRuntime, RuntimeCommandResult, RuntimeLimits, RuntimeResult, SandboxConfig


class DockerSandboxRuntime(BaseRuntime):
    def __init__(
        self,
        host_workspace: Path,
        sandbox: SandboxConfig,
        limits: RuntimeLimits,
        command_runner=None,
    ):
        super().__init__(host_workspace=host_workspace)
        self.sandbox = sandbox
        self.limits = limits
        self.command_runner = command_runner or self._run_command

    def _container_path(self, raw_path: str | Path) -> str:
        raw_str = str(raw_path).replace("\\", "/")
        workspace_root = self.sandbox.workspace_root.rstrip("/")
        if raw_str == workspace_root or raw_str.startswith(f"{workspace_root}/"):
            return raw_str
        host_path = self.resolve_host_path(raw_path)
        relative = host_path.relative_to(self.host_workspace).as_posix()
        if not relative:
            return self.sandbox.workspace_root
        return f"{self.sandbox.workspace_root}/{relative}"

    def _docker_prefix(self) -> list[str]:
        network_mode = "bridge" if self.sandbox.network_enabled else "none"
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            network_mode,
            "--cpus",
            self.limits.cpu_limit,
            "--memory",
            self.limits.memory_limit,
            "--pids-limit",
            str(self.limits.pids_limit),
            "-v",
            f"{self.host_workspace}:{self.sandbox.workspace_root}",
            "-w",
            self.sandbox.workspace_root,
            self.sandbox.image,
        ]

    async def _run_command(
        self,
        args: list[str],
        cwd: str | None = None,
        timeout: float | None = None,
        input_text: str | None = None,
    ) -> RuntimeCommandResult:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE if input_text is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input_text.encode() if input_text is not None else None),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return RuntimeCommandResult(stdout="", stderr=f"Timed out after {timeout} seconds", exit_code=124)
        return RuntimeCommandResult(
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            exit_code=proc.returncode,
        )

    async def _exec_python(self, script: str, args: list[str], timeout: float | None = None) -> RuntimeResult:
        command = self._docker_prefix() + ["python", "-c", script, *args]
        result = await self.command_runner(command, timeout=timeout)
        output = result.combined_output
        if result.exit_code != 0:
            if result.exit_code == 124:
                return RuntimeResult(output=output, is_error=True)
            if output:
                output = f"{output}\nExit code: {result.exit_code}"
            else:
                output = f"Exit code: {result.exit_code}"
        return RuntimeResult(output=output, is_error=result.exit_code != 0)

    async def exec(self, command: str, timeout: float | None = None) -> RuntimeResult:
        args = self._docker_prefix() + ["sh", "-lc", command]
        result = await self.command_runner(args, timeout=timeout)
        output = result.combined_output
        if result.exit_code != 0:
            output = f"{output}\nExit code: {result.exit_code}".strip()
        return RuntimeResult(output=output, is_error=result.exit_code != 0)

    async def read_file(
        self,
        file_path: str | Path,
        offset: int = 1,
        limit: int | None = None,
    ) -> RuntimeResult:
        container_path = self._container_path(file_path)
        script = (
            "from pathlib import Path; import sys; "
            "path = Path(sys.argv[1]); offset = max(1, int(sys.argv[2])); "
            "limit = None if sys.argv[3] == 'None' else int(sys.argv[3]); "
            "content = path.read_text(errors='replace'); "
            "lines = content.splitlines(keepends=True); start = offset - 1; "
            "end = len(lines) if limit is None else start + limit; "
            "selected = lines[start:end]; "
            "sys.stdout.write(''.join(f'{start + i + 1}\\t{line}' for i, line in enumerate(selected)))"
        )
        return await self._exec_python(script, [container_path, str(offset), str(limit)], timeout=15)

    async def write_file(self, file_path: str | Path, content: str) -> RuntimeResult:
        container_path = self._container_path(file_path)
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        script = (
            "from pathlib import Path; import sys, base64; "
            "path = Path(sys.argv[1]); path.parent.mkdir(parents=True, exist_ok=True); "
            "content = base64.b64decode(sys.argv[2]).decode('utf-8'); "
            "path.write_text(content, encoding='utf-8'); "
            "sys.stdout.write(f'Wrote {len(content)} characters to {path}')"
        )
        result = await self._exec_python(script, [container_path, encoded], timeout=15)
        if not result.is_error:
            result.metadata["chars_written"] = len(content)
        return result

    async def edit_file(
        self,
        file_path: str | Path,
        old_string: str,
        new_string: str,
    ) -> RuntimeResult:
        container_path = self._container_path(file_path)
        old_encoded = base64.b64encode(old_string.encode("utf-8")).decode("ascii")
        new_encoded = base64.b64encode(new_string.encode("utf-8")).decode("ascii")
        script = (
            "from pathlib import Path; import sys, base64; "
            "path = Path(sys.argv[1]); "
            "old = base64.b64decode(sys.argv[2]).decode('utf-8'); "
            "new = base64.b64decode(sys.argv[3]).decode('utf-8'); "
            "content = path.read_text(errors='replace'); "
            "count = content.count(old); "
            "assert count != 0, f'old_string not found in {path}'; "
            "assert count == 1, f'old_string appears {count} times in {path}; it must appear exactly once.'; "
            "path.write_text(content.replace(old, new, 1), encoding='utf-8'); "
            "sys.stdout.write(f'Replaced in {path}')"
        )
        result = await self._exec_python(script, [container_path, old_encoded, new_encoded], timeout=15)
        if result.is_error and "AssertionError:" in result.output:
            result.output = result.output.split("AssertionError:", 1)[1].strip()
        return result

    async def glob_search(self, pattern: str, path: str | Path | None = None) -> RuntimeResult:
        container_path = self._container_path(path or self.host_workspace)
        script = (
            "from pathlib import Path; import sys; "
            "base = Path(sys.argv[1]); pattern = sys.argv[2]; "
            "matches = list(base.glob(pattern)); "
            "matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True); "
            "matches = matches[:200]; "
            "sys.stdout.write('No files matched.' if not matches else '\\n'.join(str(p) for p in matches))"
        )
        return await self._exec_python(script, [container_path, pattern], timeout=20)

    async def grep_search(
        self,
        pattern: str,
        path: str | Path | None = None,
        glob_pat: str = "**/*",
        case_insensitive: bool = False,
    ) -> RuntimeResult:
        container_path = self._container_path(path or self.host_workspace)
        script = (
            dedent(
                """
                from pathlib import Path
                import re
                import sys

                base = Path(sys.argv[1])
                pattern = sys.argv[2]
                glob_pat = sys.argv[3]
                flags = re.IGNORECASE if sys.argv[4] == "1" else 0
                regex = re.compile(pattern, flags)
                files = [base] if base.is_file() else [p for p in base.glob(glob_pat) if p.is_file()]
                matches = []
                for file_path in files:
                    try:
                        lines = file_path.read_text(errors="replace").splitlines()
                    except Exception:
                        continue
                    for lineno, line in enumerate(lines, start=1):
                        if regex.search(line):
                            matches.append(f"{file_path}:{lineno}:{line}")
                        if len(matches) >= 200:
                            break
                    if len(matches) >= 200:
                        break
                sys.stdout.write("No matches found." if not matches else "\\n".join(matches))
                """
            ).strip()
        )
        return await self._exec_python(
            script,
            [container_path, pattern, glob_pat, "1" if case_insensitive else "0"],
            timeout=20,
        )


class SessionDockerRuntime(DockerSandboxRuntime):
    def __init__(
        self,
        host_workspace: Path,
        sandbox: SandboxConfig,
        limits: RuntimeLimits,
        session_name: str,
        image: str | None = None,
        command_runner=None,
    ):
        if image:
            sandbox = SandboxConfig(
                enabled=sandbox.enabled,
                image=image,
                workspace_root=sandbox.workspace_root,
                cpu_limit=sandbox.cpu_limit,
                memory_limit=sandbox.memory_limit,
                pids_limit=sandbox.pids_limit,
                network_enabled=sandbox.network_enabled,
            )
        super().__init__(
            host_workspace=host_workspace,
            sandbox=sandbox,
            limits=limits,
            command_runner=command_runner,
        )
        self.session_name = session_name
        self.container_name = f"omc-{session_name}"

    async def start(self) -> RuntimeResult:
        args = self._docker_prefix_start()
        result = await self.command_runner(args, timeout=30)
        output = result.combined_output or self.container_name
        if result.exit_code != 0:
            output = output or "Failed to start sandbox container."
        return RuntimeResult(output=output, is_error=result.exit_code != 0)

    async def close(self) -> RuntimeResult:
        args = ["docker", "rm", "-f", self.container_name]
        result = await self.command_runner(args, timeout=30)
        output = result.combined_output or self.container_name
        return RuntimeResult(output=output, is_error=result.exit_code != 0)

    async def save_snapshot(self, archive_path: Path) -> str:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        image_ref = f"ohmycode-sandbox:{self.session_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        commit_result = await self.command_runner(
            ["docker", "commit", self.container_name, image_ref],
            timeout=60,
        )
        if commit_result.exit_code != 0:
            raise RuntimeError(commit_result.combined_output or "Failed to commit sandbox container.")
        save_result = await self.command_runner(
            ["docker", "save", "-o", str(archive_path), image_ref],
            timeout=120,
        )
        if save_result.exit_code != 0:
            raise RuntimeError(save_result.combined_output or "Failed to export sandbox image.")
        return image_ref

    async def load_snapshot(self, archive_path: Path) -> RuntimeResult:
        result = await self.command_runner(["docker", "load", "-i", str(archive_path)], timeout=120)
        output = result.combined_output or ""
        return RuntimeResult(output=output, is_error=result.exit_code != 0)

    async def exec(self, command: str, timeout: float | None = None) -> RuntimeResult:
        args = ["docker", "exec", self.container_name, "sh", "-lc", command]
        result = await self.command_runner(args, timeout=timeout)
        output = result.combined_output
        if result.exit_code != 0:
            output = f"{output}\nExit code: {result.exit_code}".strip()
        return RuntimeResult(output=output, is_error=result.exit_code != 0)

    async def _exec_python(self, script: str, args: list[str], timeout: float | None = None) -> RuntimeResult:
        command = ["docker", "exec", self.container_name, "python", "-c", script, *args]
        result = await self.command_runner(command, timeout=timeout)
        output = result.combined_output
        if result.exit_code != 0:
            if result.exit_code == 124:
                return RuntimeResult(output=output, is_error=True)
            if output:
                output = f"{output}\nExit code: {result.exit_code}"
            else:
                output = f"Exit code: {result.exit_code}"
        return RuntimeResult(output=output, is_error=result.exit_code != 0)

    def _docker_prefix_start(self) -> list[str]:
        network_mode = "bridge" if self.sandbox.network_enabled else "none"
        return [
            "docker",
            "run",
            "-d",
            "--name",
            self.container_name,
            "--network",
            network_mode,
            "--cpus",
            self.limits.cpu_limit,
            "--memory",
            self.limits.memory_limit,
            "--pids-limit",
            str(self.limits.pids_limit),
            "-v",
            f"{self.host_workspace}:{self.sandbox.workspace_root}",
            "-w",
            self.sandbox.workspace_root,
            self.sandbox.image,
            "sh",
            "-lc",
            "while true; do sleep 3600; done",
        ]
