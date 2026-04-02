"""System prompt builder — assembles the system message from multiple sources."""
from __future__ import annotations
import os
import platform
from pathlib import Path
from ohmycode.tools.base import TOOL_REGISTRY

def build_system_prompt(mode: str, cwd: str, memory_content: str = "",
    project_instructions: str = "", system_prompt_append: str = "",
    sandbox_enabled: bool = False, workspace_root: str = "") -> str:
    parts: list[str] = []
    parts.append(
        "You are OhMyCode, an AI coding assistant running in the user's terminal. "
        "You help with software engineering tasks: writing code, debugging, refactoring, "
        "and explaining code. You have access to tools to read/write files, execute commands, "
        "and search the codebase. Be concise and direct."
    )
    if project_instructions:
        parts.append(f"# Project Instructions\n{project_instructions}")
    if memory_content:
        parts.append(f"# Memory\n{memory_content}")
    if sandbox_enabled:
        parts.append(
            "# Sandbox\n"
            f"- Execution is isolated in a Docker container\n"
            f"- Visible workspace root: {workspace_root or '/workspace'}\n"
            f"- Treat paths as container paths rooted at {workspace_root or '/workspace'}\n"
            "- Prefer POSIX shell commands for tool execution"
        )
        parts.append(
            "# Environment\n"
            f"- Working directory: {workspace_root or '/workspace'}\n"
            "- Platform: containerized runtime\n"
            "- Shell: POSIX sh-compatible shell\n"
            f"- Python: {platform.python_version()}"
        )
    else:
        env_info = (f"# Environment\n- Working directory: {cwd}\n"
            f"- Platform: {platform.system()} {platform.release()}\n"
            f"- Shell: {os.environ.get('SHELL', 'unknown')}\n"
            f"- Python: {platform.python_version()}")
        parts.append(env_info)
    mode_descriptions = {
        "default": "You are in DEFAULT mode. Dangerous operations (file writes, shell commands) will ask the user for confirmation.",
        "auto": "You are in AUTO mode. All tool calls are executed without user confirmation.",
        "plan": "You are in PLAN mode (read-only). You can read files and search, but CANNOT write files, edit, or execute commands.",
    }
    parts.append(f"# Mode\n{mode_descriptions.get(mode, mode_descriptions['default'])}")
    if TOOL_REGISTRY:
        tool_lines = ["# Available Tools"]
        for name, tool_cls in sorted(TOOL_REGISTRY.items()):
            tool = tool_cls()
            tool_lines.append(f"- **{name}**: {tool.description}")
        parts.append("\n".join(tool_lines))
    if system_prompt_append:
        parts.append(system_prompt_append)
    return "\n\n".join(parts)

def find_project_instructions(start_dir: str) -> str:
    current = Path(start_dir).resolve()
    for _ in range(10):
        for name in ("CLAUDE.md", "OHMYCODE.md"):
            candidate = current / name
            if candidate.is_file():
                try:
                    return candidate.read_text(encoding="utf-8")
                except OSError:
                    return ""
        parent = current.parent
        if parent == current:
            break
        current = parent
    return ""
