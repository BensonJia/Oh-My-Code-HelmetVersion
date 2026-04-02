"""Runtime abstraction for host-local and sandboxed execution."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RuntimeLimits:
    cpu_limit: str = "1.0"
    memory_limit: str = "512m"
    pids_limit: int = 256


@dataclass(frozen=True)
class SandboxConfig:
    enabled: bool = False
    image: str = "python:3.11-slim"
    workspace_root: str = "/workspace"
    cpu_limit: str = "1.0"
    memory_limit: str = "512m"
    pids_limit: int = 256
    network_enabled: bool = False

    def to_runtime_limits(self) -> RuntimeLimits:
        return RuntimeLimits(
            cpu_limit=self.cpu_limit,
            memory_limit=self.memory_limit,
            pids_limit=self.pids_limit,
        )


@dataclass
class RuntimeResult:
    output: str
    is_error: bool
    metadata: dict = field(default_factory=dict)


@dataclass
class RuntimeCommandResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def combined_output(self) -> str:
        if self.stdout and self.stderr:
            return f"{self.stdout}\n{self.stderr}"
        return self.stdout or self.stderr


class BaseRuntime:
    def __init__(self, host_workspace: Path):
        self.host_workspace = host_workspace.resolve()

    def resolve_host_path(self, raw_path: str | Path) -> Path:
        path = Path(raw_path)
        candidate = path.resolve() if path.is_absolute() else (self.host_workspace / path).resolve()
        try:
            candidate.relative_to(self.host_workspace)
        except ValueError as exc:
            raise ValueError(f"Path escapes workspace: {raw_path}") from exc
        return candidate

    async def exec(self, command: str, timeout: float | None = None) -> RuntimeResult:
        raise NotImplementedError

    async def read_file(
        self,
        file_path: str | Path,
        offset: int = 1,
        limit: int | None = None,
    ) -> RuntimeResult:
        raise NotImplementedError

    async def write_file(self, file_path: str | Path, content: str) -> RuntimeResult:
        raise NotImplementedError

    async def edit_file(
        self,
        file_path: str | Path,
        old_string: str,
        new_string: str,
    ) -> RuntimeResult:
        raise NotImplementedError

    async def glob_search(self, pattern: str, path: str | Path | None = None) -> RuntimeResult:
        raise NotImplementedError

    async def grep_search(
        self,
        pattern: str,
        path: str | Path | None = None,
        glob_pat: str = "**/*",
        case_insensitive: bool = False,
    ) -> RuntimeResult:
        raise NotImplementedError


class LocalRuntime(BaseRuntime):
    def __init__(self, host_workspace: Path):
        super().__init__(host_workspace=host_workspace)

    async def exec(self, command: str, timeout: float | None = None) -> RuntimeResult:
        import asyncio

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.host_workspace,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return RuntimeResult(
                    output=f"Command timed out after {timeout} seconds.",
                    is_error=True,
                )
            output = stdout.decode(errors="replace")
            if proc.returncode != 0:
                output = f"{output}\nExit code: {proc.returncode}".strip()
            return RuntimeResult(output=output, is_error=proc.returncode != 0)
        except Exception as exc:
            return RuntimeResult(output=f"Error executing command: {exc}", is_error=True)

    async def read_file(
        self,
        file_path: str | Path,
        offset: int = 1,
        limit: int | None = None,
    ) -> RuntimeResult:
        try:
            target = self.resolve_host_path(file_path)
        except ValueError as exc:
            return RuntimeResult(output=str(exc), is_error=True)
        try:
            content = target.read_text(errors="replace")
        except FileNotFoundError:
            return RuntimeResult(output=f"File not found: {target}", is_error=True)
        except Exception as exc:
            return RuntimeResult(output=f"Error reading file: {exc}", is_error=True)

        lines = content.splitlines(keepends=True)
        start = max(1, offset) - 1
        end = (start + limit) if limit is not None else len(lines)
        selected = lines[start:end]
        output = "".join(f"{start + i + 1}\t{line}" for i, line in enumerate(selected))
        return RuntimeResult(output=output, is_error=False)

    async def write_file(self, file_path: str | Path, content: str) -> RuntimeResult:
        try:
            target = self.resolve_host_path(file_path)
        except ValueError as exc:
            return RuntimeResult(output=str(exc), is_error=True)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return RuntimeResult(
                output=f"Wrote {len(content)} characters to {target}",
                is_error=False,
                metadata={"chars_written": len(content)},
            )
        except Exception as exc:
            return RuntimeResult(output=f"Error writing file: {exc}", is_error=True)

    async def edit_file(
        self,
        file_path: str | Path,
        old_string: str,
        new_string: str,
    ) -> RuntimeResult:
        try:
            target = self.resolve_host_path(file_path)
        except ValueError as exc:
            return RuntimeResult(output=str(exc), is_error=True)
        try:
            content = target.read_text(errors="replace")
        except FileNotFoundError:
            return RuntimeResult(output=f"File not found: {target}", is_error=True)
        except Exception as exc:
            return RuntimeResult(output=f"Error reading file: {exc}", is_error=True)

        count = content.count(old_string)
        if count == 0:
            return RuntimeResult(output=f"old_string not found in {target}", is_error=True)
        if count > 1:
            return RuntimeResult(
                output=f"old_string appears {count} times in {target}; it must appear exactly once.",
                is_error=True,
            )

        try:
            target.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
        except Exception as exc:
            return RuntimeResult(output=f"Error writing file: {exc}", is_error=True)
        return RuntimeResult(output=f"Replaced in {target}", is_error=False)

    async def glob_search(self, pattern: str, path: str | Path | None = None) -> RuntimeResult:
        try:
            base = self.resolve_host_path(path or self.host_workspace)
        except ValueError as exc:
            return RuntimeResult(output=str(exc), is_error=True)
        try:
            matches = list(base.glob(pattern))
        except Exception as exc:
            return RuntimeResult(output=f"Glob error: {exc}", is_error=True)
        matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        if not matches:
            return RuntimeResult(output="No files matched.", is_error=False)
        return RuntimeResult(output="\n".join(str(p) for p in matches[:200]), is_error=False)

    async def grep_search(
        self,
        pattern: str,
        path: str | Path | None = None,
        glob_pat: str = "**/*",
        case_insensitive: bool = False,
    ) -> RuntimeResult:
        try:
            base = self.resolve_host_path(path or self.host_workspace)
        except ValueError as exc:
            return RuntimeResult(output=str(exc), is_error=True)
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return RuntimeResult(output=f"Invalid regex: {exc}", is_error=True)

        if base.is_file():
            files = [base]
        else:
            files = [p for p in base.glob(glob_pat) if p.is_file()]

        matches: list[str] = []
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

        if not matches:
            return RuntimeResult(output="No matches found.", is_error=False)
        return RuntimeResult(output="\n".join(matches), is_error=False)
