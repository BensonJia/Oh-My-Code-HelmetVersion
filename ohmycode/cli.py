"""CLI entry: REPL and one-shot prompt mode, rich streaming output."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.text import Text

from ohmycode.config.config import load_config, OhMyCodeConfig
from ohmycode.core.loop import ConversationLoop
from ohmycode.core.messages import (
    HelmetReviewResult,
    SafetyAlert,
    TextChunk,
    ToolCallStart,
    ToolCallResult,
    TurnComplete,
)
from ohmycode.runtime.session import build_sandbox_config, create_session_runtime
from ohmycode.skills.loader import scan_skills, load_skill, SkillInfo
from ohmycode.storage.conversation import generate_conversation_id
from ohmycode.storage.sandboxes import load_sandbox_snapshot, sandbox_archive_path, save_sandbox_snapshot

console = Console()

# CLI accent: warm orange; matches toolbar mode indicator
ACCENT = "#ff6b9d"

# Claw-style block letters (cf. claw-cli startup_banner): merged rows, no multi-line pixel sprite.
# Second letter is explicit H (middle bar on row 3: ███████║), not U-shaped.
_OHMY_BLOCK_LINES = (
    " ██████╗██╗  ██╗███╗   ███╗██╗   ██╗\n"
    "██╔═══██╗██║  ██║████╗ ████║╚██╗ ██╔╝\n"
    "██║   ██║███████║██╔████╔██║ ╚████╔╝ \n"
    "██║   ██║██╔══██║██║╚██╔╝██║  ╚██╔╝  \n"
    "╚██████╔╝██║  ██║██║ ╚═╝ ██║   ██║   \n"
    " ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝   ╚═╝   "
)

# REPL input line prefix (after separator); must match _get_prompt() in run_repl
REPL_PROMPT_LINE_PREFIX = "❯  "


def _repl_prompt_prefix_display_width() -> int:
    """Terminal display width of REPL_PROMPT_LINE_PREFIX (East Asian / emoji-safe)."""
    try:
        from wcwidth import wcswidth

        w = wcswidth(REPL_PROMPT_LINE_PREFIX)
        if w >= 0:
            return w
    except ImportError:
        pass
    return len(REPL_PROMPT_LINE_PREFIX)


def _patch_pt_completion_menu_align_left(pt_session: Any) -> None:
    """Keep slash-command completion menu aligned with input (not following the cursor)."""
    try:
        from prompt_toolkit.layout import walk
        from prompt_toolkit.layout.containers import FloatContainer
        from prompt_toolkit.layout.menus import CompletionsMenu, MultiColumnCompletionsMenu
    except ImportError:
        return
    # CompletionsMenu draws each item with a leading space (see
    # prompt_toolkit.layout.menus._get_menu_item_fragments); offset the float
    # by one cell so the visible text lines up with the buffer, not the cursor.
    left = max(0, _repl_prompt_prefix_display_width() - 1)
    for container in walk(pt_session.layout.container):
        if not isinstance(container, FloatContainer):
            continue
        for fl in container.floats:
            if isinstance(fl.content, (CompletionsMenu, MultiColumnCompletionsMenu)):
                fl.left = left
                fl.xcursor = False


def _build_repl_welcome_text(
    model_display: str,
    mode: str,
    n_skills: int,
    sandbox_status: str,
) -> Text:
    """Claw-inspired: big block letters + subtitle + aligned meta rows."""
    t = Text()
    t.append(_OHMY_BLOCK_LINES, style=ACCENT)
    t.append("  ")
    t.append("OhMyCode", style=f"bold {ACCENT}")
    t.append(" -- 🪖Helmet Version 0.1.0", style="dim")
    t.append("\n\n")
    label_w = 12
    t.append("Model".ljust(label_w), style="dim")
    t.append(f"{model_display}\n", style="bold")
    t.append("Mode".ljust(label_w), style="dim")
    t.append(f"{mode}\n", style="green")
    t.append("Skills".ljust(label_w), style="dim")
    t.append(f"{n_skills} available\n", style="dim")
    t.append("Sandbox".ljust(label_w), style="dim")
    t.append(f"{sandbox_status}\n", style="dim" if sandbox_status == "not available" else "bold")
    return t


def _build_sandbox_status(
    config: OhMyCodeConfig,
    session_runtime: Any,
    docker_available: bool | None = None,
) -> str:
    if not config.sandbox.enabled:
        return "not available"
    if docker_available is None:
        docker_available = shutil.which("docker") is not None
    if not docker_available:
        return "not available"

    sandbox = getattr(session_runtime, "sandbox", config.sandbox)
    container_name = getattr(session_runtime, "container_name", "not loaded")
    network = "on" if getattr(sandbox, "network_enabled", False) else "off"
    return (
        f"{container_name} | {sandbox.image} | "
        f"cpu={sandbox.cpu_limit} | mem={sandbox.memory_limit} | net={network}"
    )


# ── Argument parsing ────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ohmycode",
        description="OhMyCode — a minimal AI coding assistant",
    )
    parser.add_argument(
        "-p", "--prompt",
        metavar="PROMPT",
        help="Run a single prompt and exit (non-interactive mode).",
    )
    parser.add_argument(
        "--mode",
        metavar="MODE",
        choices=["default", "auto", "plan"],
        help="Permission mode: default | auto | plan.",
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const="",
        default=None,
        help="Resume a previous conversation",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        help="Subcommand: vchange [-N|N]",
    )
    parser.add_argument(
        "command_arg",
        nargs="?",
        default=None,
        help="Argument for subcommand",
    )
    return parser.parse_args(argv)


# ── Version switch (vchange) ──────────────────────────────────────────────────


def run_vchange(step: int | None = None) -> int:
    """Version switch: step=None shows status, step=-1 goes back, step=1 goes forward. Returns exit code."""
    import os
    import subprocess

    cwd = os.getcwd()

    # Check git
    r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                       capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        console.print("[red]Not in a git repository.[/red]")
        return 1

    if step is None:
        # Show current position
        log = subprocess.run(["git", "log", "--oneline", "-5"],
                             capture_output=True, text=True, cwd=cwd)
        head = subprocess.run(["git", "rev-parse", "HEAD"],
                              capture_output=True, text=True, cwd=cwd).stdout.strip()
        console.print(f"\n  [bold]Recent commits:[/]")
        for line in log.stdout.strip().splitlines():
            sha = line.split()[0]
            if head.startswith(sha):
                console.print(f"    [green]▸ {line}[/]  [green]← HEAD[/]")
            else:
                console.print(f"    [dim]  {line}[/]")
        console.print(f"\n  [dim]Usage: ohmycode vchange -1 (back) / ohmycode vchange 1 (forward)[/]")
        return 0

    if step == 0:
        console.print("[dim]Nothing to do.[/dim]")
        return 0

    # Full commit history on main (oldest to newest)
    all_log = subprocess.run(["git", "log", "main", "--oneline", "--reverse"],
                             capture_output=True, text=True, cwd=cwd)
    all_commits = all_log.stdout.strip().splitlines()
    if not all_commits:
        console.print("[yellow]No commits found.[/yellow]")
        return 1

    head_sha = subprocess.run(["git", "rev-parse", "HEAD"],
                              capture_output=True, text=True, cwd=cwd).stdout.strip()
    current_idx = -1
    for i, line in enumerate(all_commits):
        sha = line.split()[0]
        if head_sha.startswith(sha):
            current_idx = i
            break

    if current_idx == -1:
        console.print("[yellow]HEAD is not on main branch history.[/yellow]")
        return 1

    target_idx = current_idx + step
    if target_idx < 0:
        console.print("[yellow]Already at the oldest commit. Cannot go back further.[/yellow]")
        return 1
    if target_idx >= len(all_commits):
        console.print("[yellow]Already at the latest commit. Cannot go forward.[/yellow]")
        return 1

    target_line = all_commits[target_idx]
    target_sha = target_line.split()[0]

    console.print(f"\n  [bold]Current:[/] {all_commits[current_idx]}")
    console.print(f"  [bold]Target: [/] {target_line}")

    # Warn about uncommitted changes
    status = subprocess.run(["git", "status", "--porcelain"],
                            capture_output=True, text=True, cwd=cwd)
    if status.stdout.strip():
        n = len(status.stdout.strip().splitlines())
        console.print(f"  [yellow]Warning: {n} uncommitted change{'s' if n > 1 else ''} will be lost[/yellow]")

    console.print("  [bold]Confirm? (y/n):[/bold] ", end="")
    answer = input().strip().lower()
    if answer == "y":
        subprocess.run(["git", "checkout", target_sha, "--force"],
                       capture_output=True, text=True, cwd=cwd)
        console.print(f"  [green]✓ Switched to: {target_line}[/green]")
        console.print("  [dim]Restart ohmycode to load the changed code.[/dim]")
        return 0
    else:
        console.print("  [dim]Cancelled.[/dim]")
        return 0


# ── Tool confirmation ───────────────────────────────────────────────────────────


async def confirm_tool_call(tool_name: str, params: dict) -> str:
    """Show tool call details to the user and read y/n/a/h response."""
    params_preview = json.dumps(params, ensure_ascii=False)
    if len(params_preview) > 120:
        params_preview = params_preview[:117] + "..."

    console.print()
    console.print(f"  [bold yellow]⚠  Allow [{ACCENT}]{escape(tool_name)}[/]?[/]", highlight=False)
    console.print(f"  [dim]{escape(params_preview)}[/dim]", highlight=False)
    console.print()
    console.print(
        "  [bold]y[/][dim]es[/]  ·  [bold]n[/][dim]o[/]  ·  "
        "[bold]a[/][dim]lways[/]  ·  ask [bold]H[/][dim]elmet[/]  ",
        end="",
    )

    loop = asyncio.get_event_loop()
    try:
        answer = await loop.run_in_executor(None, sys.stdin.readline)
        return answer.strip().lower()[:1] or "n"
    except (EOFError, KeyboardInterrupt):
        return "n"


async def confirm_safety_review(review: Any) -> str:
    """Show safety alert details and read y/n/a/h response."""
    console.print()
    if getattr(review, "review_activity", ""):
        console.print(f"  [dim]{escape(review.review_activity)}[/dim]", highlight=False)
    console.print(
        f"  [bold red]Safety pause:[/] [{ACCENT}]{escape(review.tool_name)}[/] "
        f"[bold]{escape(review.severity)}[/]",
        highlight=False,
    )
    console.print(f"  [dim]{escape(review.reason)}[/dim]", highlight=False)
    console.print(
        "  [bold]y[/][dim]es[/]  路  [bold]n[/][dim]o[/]  路  "
        "[bold]a[/][dim]lways[/]  路  ask [bold]H[/][dim]elmet[/]  ",
        end="",
    )

    loop = asyncio.get_event_loop()
    try:
        answer = await loop.run_in_executor(None, sys.stdin.readline)
        return answer.strip().lower()[:1] or "n"
    except (EOFError, KeyboardInterrupt):
        return "n"


async def confirm_yes_no(prompt: str, default: str = "n") -> str:
    console.print()
    console.print(f"  [bold]{escape(prompt)}[/] ", end="", highlight=False)
    loop = asyncio.get_event_loop()
    try:
        answer = await loop.run_in_executor(None, sys.stdin.readline)
        return answer.strip().lower()[:1] or default
    except (EOFError, KeyboardInterrupt):
        return default


# ── Stream rendering ──────────────────────────────────────────────────────────


async def render_stream(conv: ConversationLoop) -> str:
    """Consume run_turn() event stream, render to terminal, return finish_reason."""
    import time

    finish_reason = "stop"
    text_printed = False
    tool_count = 0

    # ── "Thinking" spinner (write to sys.stdout directly, not rich.Live) ──
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    thinking = True
    t_start = time.monotonic()
    spinner_task = None

    async def _spinner():
        idx = 0
        try:
            while True:
                elapsed = time.monotonic() - t_start
                frame = SPINNER_FRAMES[idx % len(SPINNER_FRAMES)]
                # \r to start of line, \033[K clear to end of line
                sys.stdout.write(f"\r  \033[2m{frame} Thinking... {elapsed:.0f}s\033[0m\033[K")
                sys.stdout.flush()
                idx += 1
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            # Clear spinner line
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    spinner_task = asyncio.create_task(_spinner())

    async for event in conv.run_turn():
        # Stop spinner when first real event arrives
        if thinking:
            thinking = False
            if spinner_task and not spinner_task.done():
                spinner_task.cancel()
                try:
                    await spinner_task
                except asyncio.CancelledError:
                    pass

        if isinstance(event, TextChunk):
            # Stream print with indent
            text = event.text
            if not text_printed:
                # After tool calls: newline + bullet marker
                if tool_count > 0:
                    console.print(f"\n  [bold {ACCENT}]●[/] ", end="", highlight=False)
                else:
                    console.print("  ", end="", highlight=False)
            # Add 4-space indent after each newline
            text = text.replace("\n", "\n    ")
            console.print(text, end="", highlight=False)
            text_printed = True

        elif isinstance(event, ToolCallStart):
            if text_printed:
                console.print()  # Newline to separate from text
                text_printed = False

            # Show tool call in a compact format
            tool_display = event.tool_name
            params_str = json.dumps(event.params, ensure_ascii=False)
            if len(params_str) > 100:
                params_str = params_str[:97] + "..."
            console.print(
                f"\n    [bold {ACCENT}]▸[/] [bold]{escape(tool_display)}[/]  [dim]{escape(params_str)}[/]",
                highlight=False,
            )
            tool_count += 1

        elif isinstance(event, HelmetReviewResult):
            console.print(
                f"    [bold {ACCENT}]Helmet[/] [bold]{escape(event.severity)}[/] "
                f"[dim]{escape(event.summary)}[/dim]",
                highlight=False,
            )
            console.print(
                f"    [dim]Expected effect:[/] {escape(event.expected_effect)}",
                highlight=False,
            )
            console.print(
                f"    [dim]Recommendation:[/] {escape(event.recommendation)}",
                highlight=False,
            )

        elif isinstance(event, SafetyAlert):
            if event.review_activity:
                console.print(
                    f"    [dim]{escape(event.review_activity)}[/dim]",
                    highlight=False,
                )
            console.print(
                f"    [bold red]警[/] [bold]{escape(event.tool_name)}[/] "
                f"[red]{escape(event.severity)}[/] [dim]{escape(event.reason)}[/dim]",
                highlight=False,
            )

        elif isinstance(event, ToolCallResult):
            raw = event.result
            max_lines = 10
            lines = raw.splitlines()
            # Indent each line by 4 spaces; escape so tool output cannot break Rich markup
            if len(lines) > max_lines:
                indented = "\n".join("    " + l for l in lines[:max_lines])
                output = escape(indented) + f"\n    [dim]... ({len(lines)} lines total)[/dim]"
            else:
                body = raw
                if len(body) > 500:
                    body = body[:497] + "..."
                body = "\n".join("    " + l for l in body.splitlines())
                output = escape(body)

            if event.is_error:
                console.print(f"    [red]✗[/] [red]{output}[/]", highlight=False)
            else:
                console.print(f"    [green]✓[/]\n[dim]{output}[/]", highlight=False)

        elif isinstance(event, TurnComplete):
            finish_reason = event.finish_reason
            if text_printed:
                console.print()  # Final newline
                text_printed = False
            u = event.usage
            elapsed = time.monotonic() - t_start
            # Stats line: tool count · tokens · elapsed
            stats_parts = []
            if tool_count > 0:
                stats_parts.append(f"{tool_count} tool use{'s' if tool_count > 1 else ''}")
            if u.total_tokens > 0:
                stats_parts.append(f"{u.total_tokens:,} tokens")
            stats_parts.append(f"{elapsed:.1f}s")
            console.print(f"\n  [dim]{' · '.join(stats_parts)}[/dim]")
            tool_count = 0

    return finish_reason


# ── One-shot prompt mode ─────────────────────────────────────────────────────


async def run_single(prompt: str, config_overrides: dict[str, Any]) -> int:
    """Run a single prompt then exit; returns exit code."""
    config = load_config(config_overrides)
    conv = ConversationLoop(
        config=config,
        confirm_fn=confirm_tool_call,
        safety_confirm_fn=confirm_safety_review,
    )
    conv.initialize()
    conv.add_user_message(prompt)

    try:
        finish_reason = await render_stream(conv)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        return 130

    return 0


# ── REPL mode ─────────────────────────────────────────────────────────────────


async def run_repl(config_overrides: dict[str, Any]) -> int:
    """Interactive REPL loop; supports /exit, /clear, /mode, etc."""
    config = load_config(config_overrides)
    available_skills = scan_skills()
    resume_messages = None
    resume_metadata = None
    session_id = generate_conversation_id()

    # Resume conversation
    if "_resume" in config_overrides and config_overrides["_resume"] is not None:
        from ohmycode.storage.conversation import load_conversation
        result = load_conversation(config_overrides.get("_resume", ""))
        if result:
            resume_messages, resume_metadata = result
            session_id = Path(resume_metadata.get("filename", f"{session_id}.json")).stem
        else:
            console.print("[yellow]No conversation found to resume.[/yellow]\n")

    session_runtime = None
    if config.sandbox.enabled:
        snapshot = load_sandbox_snapshot(session_id) if resume_metadata else None
        restore_snapshot = False
        if snapshot is not None:
            answer = await confirm_yes_no(
                f"Restore saved sandbox for session {session_id}? (y/n)",
                default="y",
            )
            restore_snapshot = answer == "y"
        session_runtime = await create_session_runtime(
            host_workspace=Path.cwd(),
            sandbox=build_sandbox_config(config.sandbox),
            session_name=session_id,
            snapshot=snapshot if restore_snapshot else None,
        )

    conv = ConversationLoop(
        config=config,
        confirm_fn=confirm_tool_call,
        safety_confirm_fn=confirm_safety_review,
        runtime_override=session_runtime,
    )
    conv.initialize()
    if resume_messages is not None:
        conv.messages = resume_messages
        console.print(f"[dim]Resumed conversation {session_id}[/dim]\n")

    # Welcome banner (Claw-inspired: block letters + meta rows; no pixel sprite)
    from rich.panel import Panel
    from rich import box as rich_box

    import re
    model_display = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", config.model)
    sandbox_status = _build_sandbox_status(config, session_runtime)

    welcome_body = _build_repl_welcome_text(
        model_display=model_display,
        mode=config.mode,
        n_skills=len(available_skills),
        sandbox_status=sandbox_status,
    )

    banner = Panel(
        welcome_body,
        title=f"[bold {ACCENT}]◆ Code -- 🪖Helmet Version 0.1.0[/]",
        title_align="left",
        border_style=ACCENT,
        box=rich_box.ROUNDED,
        padding=(2, 2),
    )
    console.print()
    console.print(banner)
    console.print()
    console.print(
        f"  [dim]Type[/] [bold {ACCENT}]/skills[/] [dim]for commands ·[/] "
        f"[bold {ACCENT}]/status[/] [dim]for context usage ·[/] [bold {ACCENT}]/exit[/] "
        f"[dim]to quit ·[/] [bold]Ctrl+C[/] [dim]to cancel[/]"
    )
    console.print()

    # Try prompt_toolkit; fall back to input()
    use_prompt_toolkit = False
    pt_session = None
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.styles import Style as PTStyle

        def _truncate(text: str, max_len: int = 50) -> str:
            return text[:max_len - 1] + "…" if len(text) > max_len else text

        class SlashCompleter(Completer):
            _BUILTIN = {
                "/exit": "Quit",
                "/clear": "Clear conversation",
                "/mode": "Switch mode (default|auto|plan)",
                "/status": "Show context and session status",
                "/memory": "Manage memories",
                "/vchange": "Version switch (-1 back / 1 forward)",
                "/skills": "List all skills",
            }

            def __init__(self, skills: dict[str, SkillInfo]) -> None:
                self._skills = skills

            def get_completions(self, document, complete_event):
                text = document.text_before_cursor
                if not text.startswith("/"):
                    return
                offset = len(text)
                for cmd, desc in self._BUILTIN.items():
                    if cmd.startswith(text):
                        yield Completion(
                            cmd, start_position=-offset,
                            display=HTML(f"<b>{cmd}</b>"),
                            display_meta=desc,
                        )
                for skill_name, info in sorted(self._skills.items()):
                    full = f"/{skill_name}"
                    if full.startswith(text):
                        yield Completion(
                            full, start_position=-offset,
                            display=HTML(f"<ansicyan>{full}</ansicyan>"),
                            display_meta=_truncate(info.description),
                        )

        # prompt_toolkit styles
        pt_style = PTStyle.from_dict({
            # Completion menu
            "completion-menu": "noinherit",
            "completion-menu.completion": "noinherit fg:#bbbbbb",
            "completion-menu.completion.current": f"noinherit noreverse fg:{ACCENT} bold",
            "completion-menu.meta.completion": "noinherit fg:#666666",
            "completion-menu.meta.completion.current": f"noinherit noreverse fg:{ACCENT}",
            "scrollbar.background": "noinherit",
            "scrollbar.button": "noinherit",
            # Input area
            "prompt": "fg:#888888",
            "separator": "fg:#444444",
            "bottom-toolbar": "bg:default fg:default noreverse",
            "bottom-toolbar.text": "noreverse",
            "mode-indicator": f"fg:{ACCENT} bold",
            "mode-text": "fg:#888888",
            "tool-count": "fg:#00d4aa",
            "hint": "fg:#555555",
        })

        # Terminal width
        import shutil
        _term_width = shutil.get_terminal_size().columns

        def _get_toolbar():
            """Bottom toolbar: mode · context · skill count · hint"""
            from prompt_toolkit.formatted_text import FormattedText
            mode_label = current_mode
            tool_total = len(available_skills)
            status = conv.get_status_snapshot()
            context_label = f"{status['usage_percent']:.1f}% ctx"
            parts = [
                ("class:mode-indicator", "  ▸▸ "),
                ("class:mode-text", f"{mode_label} mode"),
                ("class:hint", " · "),
                ("class:tool-count", context_label),
                ("class:hint", " · "),
                ("class:tool-count", f"{tool_total}"),
                ("class:mode-text", f" skill{'s' if tool_total != 1 else ''}"),
                ("class:hint", " · "),
                ("class:hint", "↓ to complete"),
            ]
            return FormattedText(parts)

        def _get_prompt():
            """Prompt: separator line + ❯"""
            from prompt_toolkit.formatted_text import FormattedText
            sep = "─" * _term_width
            return FormattedText([
                ("class:separator", sep + "\n"),
                ("", REPL_PROMPT_LINE_PREFIX),
            ])

        from prompt_toolkit.filters import Condition

        history_dir = Path.home() / ".ohmycode"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_path = str(history_dir / "history")

        _completer = SlashCompleter(available_skills)

        pt_session = PromptSession(
            history=FileHistory(history_path),
            completer=_completer,
            style=pt_style,
            complete_while_typing=Condition(
                lambda: (
                    pt_session.app.current_buffer.text.startswith("/")
                    and " " not in pt_session.app.current_buffer.text
                )
            ),
            bottom_toolbar=_get_toolbar,
            prompt_continuation="   ",
        )
        _patch_pt_completion_menu_align_left(pt_session)
        use_prompt_toolkit = True
    except ImportError:
        pass

    def _repl_print(*args: Any, **kwargs: Any) -> None:
        """Send Rich output through patch_stdout when using prompt_toolkit.

        Raw console.print between prompts desyncs the terminal cursor from PT's
        renderer; macOS IME (e.g. Chinese) often breaks after large prints
        (e.g. /skills). patch_stdout hides/restores the prompt layer correctly.
        """
        if use_prompt_toolkit and pt_session is not None:
            from prompt_toolkit.patch_stdout import patch_stdout

            with patch_stdout():
                console.print(*args, **kwargs)
        else:
            console.print(*args, **kwargs)

    def _repl_print_plain(*args: Any, **kwargs: Any) -> None:
        """Plain print (no Rich/ANSI). Use when patch_stdout breaks escape sequences."""
        if use_prompt_toolkit and pt_session is not None:
            from prompt_toolkit.patch_stdout import patch_stdout

            with patch_stdout():
                print(*args, **kwargs, flush=True)
        else:
            print(*args, **kwargs, flush=True)

    async def _read_line() -> str | None:
        if use_prompt_toolkit and pt_session is not None:
            try:
                return await pt_session.prompt_async(_get_prompt)
            except (EOFError, KeyboardInterrupt):
                return None
        else:
            loop = asyncio.get_event_loop()
            try:
                line = await loop.run_in_executor(None, lambda: input("❯ "))
                return line
            except (EOFError, KeyboardInterrupt):
                return None

    current_mode = config.mode

    async def _finalize_session() -> int:
        nonlocal session_runtime
        save_sandbox = False
        if config.sandbox.enabled and session_runtime is not None:
            answer = await confirm_yes_no(
                f"Save sandbox locally for session {session_id}? (y/n)",
                default="n",
            )
            save_sandbox = answer == "y"

        if conv.messages or save_sandbox:
            from ohmycode.storage.conversation import save_conversation

            save_conversation(
                conv.messages,
                config.provider,
                config.model,
                config.mode,
                conversation_id=session_id,
            )
            _repl_print_plain("Conversation saved.")

            if save_sandbox and session_runtime is not None:
                archive_path = sandbox_archive_path(session_id)
                image_ref = await session_runtime.save_snapshot(archive_path)
                sandbox_cfg = (
                    session_runtime.sandbox.__dict__
                    if hasattr(session_runtime.sandbox, "__dict__")
                    else (
                        config.sandbox.model_dump()
                        if hasattr(config.sandbox, "model_dump")
                        else config.sandbox.dict()
                    )
                )
                save_sandbox_snapshot(
                    session_name=session_id,
                    archive_path=archive_path,
                    image_ref=image_ref,
                    sandbox_config=sandbox_cfg,
                )
                _repl_print_plain(f"Sandbox saved: {archive_path}")

        if session_runtime is not None:
            await session_runtime.close()
            session_runtime = None

        if conv.messages and conv._provider:
            try:
                from ohmycode.memory.memory import extract_memories_from_conversation, save_memory
                memories = await extract_memories_from_conversation(
                    conv.messages, conv._provider, config.model
                )
                for m in memories:
                    save_memory(m["name"], m["type"], m["content"])
            except Exception:
                pass
        return 0

    while True:
        try:
            user_input = await _read_line()
        except KeyboardInterrupt:
            _repl_print("\n[yellow](Use /exit to quit)[/yellow]")
            continue

        if user_input is None:
            # EOF
            _repl_print_plain("\nGoodbye.")
            return await _finalize_session()

        user_input = user_input.strip()
        if not user_input:
            continue

        # ── Slash commands ───────────────────────────────────────────────
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()

            if cmd == "/exit":
                _repl_print_plain("Goodbye.")
                return await _finalize_session()

            elif cmd == "/clear":
                conv.messages.clear()
                conv.auto_approved.clear()
                _repl_print("[dim]Conversation cleared.[/dim]")
                continue

            elif cmd == "/mode":
                if len(parts) < 2:
                    _repl_print(f"[dim]Current mode: {current_mode}[/dim]")
                    _repl_print("[dim]Usage: /mode <default|auto|plan>[/dim]")
                else:
                    new_mode = parts[1].strip()
                    if new_mode not in ("default", "auto", "plan"):
                        _repl_print(f"[red]Unknown mode: {new_mode}[/red]")
                    else:
                        current_mode = new_mode
                        # Rebuild config and loop to apply new mode
                        new_overrides = dict(config_overrides)
                        new_overrides["mode"] = current_mode
                        config = load_config(new_overrides)
                        conv = ConversationLoop(
                            config=config,
                            confirm_fn=confirm_tool_call,
                            safety_confirm_fn=confirm_safety_review,
                            runtime_override=session_runtime,
                        )
                        conv.initialize()
                        _repl_print(f"[dim]Mode switched to: {current_mode}[/dim]")
                continue

            elif cmd == "/status":
                status = conv.get_status_snapshot()
                _repl_print()
                _repl_print("  [bold]Session status[/]")
                _repl_print(
                    f"    [dim]Model:[/] {status['provider']} / {status['model']}    "
                    f"[dim]Mode:[/] {status['mode']}"
                )
                _repl_print(
                    f"    [dim]Messages:[/] {status['message_count']}    "
                    f"[dim]Context:[/] {status['used_tokens']:,} / {status['effective_window']:,} tokens "
                    f"([bold]{status['usage_percent']:.1f}%[/])"
                )
                _repl_print(
                    f"    [dim]Budget:[/] {status['token_budget']:,} total, "
                    f"{status['output_reserved']:,} reserved for output"
                )
                _repl_print(
                    f"    [dim]Compression stage:[/] {status['compression_stage']}"
                )
                _repl_print()
                continue

            elif user_input.startswith("/memory"):
                parts = user_input.split(maxsplit=2)
                from ohmycode.memory.memory import list_memories, delete_memory
                if len(parts) == 1 or parts[1] == "list":
                    memories = list_memories()
                    if memories:
                        for m in memories:
                            _repl_print(f"  [{m['type']}] {m['name']} ({m['filename']})")
                    else:
                        _repl_print("[dim]No memories saved.[/dim]")
                elif parts[1] == "delete" and len(parts) > 2:
                    if delete_memory(parts[2]):
                        _repl_print(f"[dim]Deleted {parts[2]}[/dim]")
                    else:
                        _repl_print(f"[yellow]Memory not found: {parts[2]}[/yellow]")
                continue

            elif cmd == "/vchange":
                arg = parts[1].strip() if len(parts) > 1 else None
                step = None
                if arg is not None:
                    try:
                        step = int(arg)
                    except ValueError:
                        _repl_print("[red]Usage: /vchange [-N|N]  (e.g. /vchange -1)[/red]")
                        continue
                run_vchange(step)
                continue

            elif cmd == "/skills":
                if available_skills:
                    _repl_print("\n  [bold]Available skills:[/]")
                    # Longest skill name for column alignment
                    max_name = max(len(s) for s in available_skills) + 1
                    for skill_name, info in sorted(available_skills.items()):
                        padded = f"/{skill_name}".ljust(max_name + 1)
                        desc = info.description
                        # Truncate description to 60 chars
                        if len(desc) > 60:
                            desc = desc[:57] + "..."
                        _repl_print(f"    [cyan]{padded}[/] [dim]{desc}[/]")
                    _repl_print()
                else:
                    _repl_print("[dim]No skills found.[/dim]")
                continue

            else:
                skill_name = cmd.lstrip("/")
                if skill_name in available_skills:
                    arguments = parts[1] if len(parts) > 1 else ""
                    skill_content = load_skill(available_skills[skill_name], arguments=arguments)
                    conv.add_user_message(skill_content)
                    try:
                        finish_reason = await render_stream(conv)
                        if finish_reason == "max_turns":
                            _repl_print("[yellow]Reached maximum turns limit.[/yellow]")
                    except KeyboardInterrupt:
                        conv.cancel()
                        _repl_print("\n[yellow](Generation cancelled. Continue or /exit)[/yellow]")
                else:
                    _repl_print(f"[red]Unknown command: {cmd}[/red]")
                    _repl_print("[dim]Available: /exit /clear /mode /status /memory /skills[/dim]")
                continue

        # ── Normal user message ──────────────────────────────────────────
        conv.add_user_message(user_input)

        gen_task: asyncio.Task | None = None
        try:
            finish_reason = await render_stream(conv)
            if finish_reason == "max_turns":
                _repl_print(
                    "[yellow]Reached maximum turns limit.[/yellow]"
                )
        except KeyboardInterrupt:
            conv.cancel()
            _repl_print("\n[yellow](Generation cancelled. Continue or /exit)[/yellow]")

    return await _finalize_session()


# ── Main entry ────────────────────────────────────────────────────────────────


def run() -> int:
    """CLI main: parse args, run run_single, run_repl, or subcommands."""
    args = parse_args()

    # Subcommand: ohmycode vchange [-1|1|...]
    if args.command == "vchange":
        step = None
        if args.command_arg is not None:
            try:
                step = int(args.command_arg)
            except ValueError:
                console.print("[red]Usage: ohmycode vchange [-N|N]  (e.g. ohmycode vchange -1)[/red]")
                return 1
        return run_vchange(step)

    config_overrides: dict[str, Any] = {
        "mode": args.mode,
    }

    if args.resume is not None:
        config_overrides["_resume"] = args.resume

    if args.prompt:
        return asyncio.run(run_single(args.prompt, config_overrides))
    else:
        return asyncio.run(run_repl(config_overrides))
