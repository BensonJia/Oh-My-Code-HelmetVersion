"""Async conversation loop with tool execution and permission checks."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator, Callable, Awaitable, Any

from ohmycode.core.messages import (
    HelmetReviewResult,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    ToolUseBlock,
    TextChunk,
    SafetyAlert,
    ToolCallStart,
    ToolCallResult,
    TurnComplete,
    TokenUsage,
    StreamEvent,
    Message,
)
from ohmycode.core.safety import SafetyEngine
from ohmycode.core.context import ContextManager
from ohmycode.core.permissions import check_permission
from ohmycode.core.system_prompt import build_system_prompt, find_project_instructions
from ohmycode.providers.base import get_provider, auto_import_providers
from ohmycode.runtime.base import SandboxConfig
from ohmycode.runtime.docker import DockerSandboxRuntime
from ohmycode.tools.base import auto_import_tools, get_tool_defs, run_tool_calls, ToolContext
from ohmycode.config.config import OhMyCodeConfig


class ConversationLoop:
    """Core loop driving multi-turn conversation (including tool calls)."""

    def __init__(
        self,
        config: OhMyCodeConfig,
        confirm_fn: Callable[[str, dict], Awaitable[str]] | None = None,
        safety_confirm_fn: Callable[[Any], Awaitable[str] | str] | None = None,
        runtime_override: Any = None,
        agent_depth: int = 0,
        cwd_override: str | None = None,
        is_sub_agent: bool = False,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.confirm_fn = confirm_fn
        self.safety_confirm_fn = safety_confirm_fn
        self.messages: list[Message] = []
        self.auto_approved: dict[str, bool] = {}
        self.safety_auto_approved: dict[str, bool] = {}
        self._cancelled: bool = False
        self._provider: Any = None
        self._reviewer_provider: Any = None
        self._system_prompt: str = ""
        self._runtime: Any = runtime_override
        self._agent_depth = agent_depth
        self._cwd_override = cwd_override
        self._is_sub_agent = is_sub_agent
        self._extra_context = dict(extra_context or {})
        self._safety_engine = SafetyEngine(config.safety)
        self.context_mgr = ContextManager(
            token_budget=config.token_budget,
            output_reserved=config.output_tokens_reserved,
        )

    def initialize(self) -> None:
        """Initialize: import providers/tools, create provider, build system prompt."""
        auto_import_providers()
        auto_import_tools()

        provider_kwargs = self._build_provider_kwargs(self.config)
        self._provider = get_provider(self.config.provider, **provider_kwargs)
        self._reviewer_provider = self._provider
        reviewer_cfg = self.config.safety.llm_reviewer
        if reviewer_cfg.enabled:
            reviewer_kwargs = self._build_provider_kwargs(reviewer_cfg)
            same_service = (
                reviewer_cfg.provider == self.config.provider
                and reviewer_kwargs == provider_kwargs
            )
            if not same_service:
                self._reviewer_provider = get_provider(reviewer_cfg.provider, **reviewer_kwargs)

        from ohmycode.memory.memory import load_memory_index, BTreeMemoryStore, get_project_memory_dir
        from ohmycode.memory.recall import RecallEngine

        cwd = self._cwd_override or os.getcwd()
        project_instructions = find_project_instructions(cwd)
        sandbox_data = (
            self.config.sandbox.model_dump()
            if hasattr(self.config.sandbox, "model_dump")
            else self.config.sandbox.dict()
        )
        sandbox = SandboxConfig(**sandbox_data)
        if self._runtime is not None:
            pass
        elif sandbox.enabled:
            self._runtime = DockerSandboxRuntime(
                host_workspace=Path(cwd),
                sandbox=sandbox,
                limits=sandbox.to_runtime_limits(),
            )
        else:
            from ohmycode.runtime.base import LocalRuntime

            self._runtime = LocalRuntime(Path(cwd))

        # Try B+-Tree memory first; fall back to legacy flat index
        try:
            mem_dir = get_project_memory_dir(cwd)
            self._memory_store = BTreeMemoryStore(mem_dir)
            self._memory_store.ensure_tree()
            self._recall_engine = RecallEngine(self._memory_store)
            memory_content = self._memory_store.get_root_index()
        except Exception:
            self._memory_store = None
            self._recall_engine = None
            memory_content = load_memory_index()

        self._system_prompt = build_system_prompt(
            mode=self.config.mode,
            cwd=cwd,
            project_instructions=project_instructions,
            memory_content=memory_content,
            system_prompt_append=self.config.system_prompt_append,
            sandbox_enabled=self.config.sandbox.enabled,
            workspace_root=self.config.sandbox.workspace_root,
        )

    def add_user_message(self, content: str) -> None:
        """Append a user message to conversation history."""
        self.messages.append(UserMessage(content=content))

    def cancel(self) -> None:
        """Set cancel flag so run_turn() exits on the next check."""
        self._cancelled = True

    def get_status_snapshot(self) -> dict[str, Any]:
        """Return current conversation/context usage stats for /status."""
        used_tokens = self.context_mgr.count_tokens(self.messages, self._system_prompt)
        effective_window = max(1, self.config.token_budget - self.config.output_tokens_reserved)
        usage_ratio = self.context_mgr.get_usage_ratio(self.messages, self._system_prompt)
        usage_percent = round(usage_ratio * 100, 1)

        if usage_ratio >= 0.90:
            compression_stage = "auto_compact"
        elif usage_ratio >= 0.85:
            compression_stage = "collapse"
        elif usage_ratio >= 0.80:
            compression_stage = "micro_compact"
        elif usage_ratio >= 0.75:
            compression_stage = "snip"
        else:
            compression_stage = "ok"

        return {
            "message_count": len(self.messages),
            "used_tokens": used_tokens,
            "token_budget": self.config.token_budget,
            "output_reserved": self.config.output_tokens_reserved,
            "effective_window": effective_window,
            "usage_ratio": usage_ratio,
            "usage_percent": usage_percent,
            "compression_stage": compression_stage,
            "mode": self.config.mode,
            "provider": self.config.provider,
            "model": self.config.model,
        }

    async def run_turn(self) -> AsyncIterator[StreamEvent]:
        """Run one conversation turn (may include multiple tool round-trips).

        Yields StreamEvent for the caller (CLI) to render.
        """
        self._cancelled = False
        turn_count = 0
        max_turns = self.config.max_turns

        tool_defs = get_tool_defs()

        # Prepare tool execution context
        ctx = ToolContext(
            mode=self.config.mode,
            agent_depth=self._agent_depth,
            cwd=self._cwd_override or os.getcwd(),
            is_sub_agent=self._is_sub_agent,
            extra=self._extra_context.copy(),
            runtime=self._runtime,
            workspace_root=self.config.sandbox.workspace_root,
            config=self.config,
        )

        # Latest usage (updated after each provider call)
        last_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        last_finish_reason = "stop"

        while turn_count < max_turns and not self._cancelled:
            turn_count += 1

            # ── Context compression (if needed) ────────────────────────────────
            try:
                self.messages = await self.context_mgr.maybe_compress(
                    self.messages, self._system_prompt, self._provider, self.config.model
                )
            except RuntimeError:
                yield TurnComplete(finish_reason="error", usage=TokenUsage(0, 0, 0))
                return

            # ── Call provider.stream() ───────────────────────────────────────
            collected_text = ""
            collected_tool_calls: list[ToolCallStart] = []

            try:
                async for event in self._provider.stream(
                    messages=self.messages,
                    tools=tool_defs,
                    system=self._system_prompt,
                    model=self.config.model,
                ):
                    if self._cancelled:
                        break

                    if isinstance(event, TextChunk):
                        collected_text += event.text
                        yield event

                    elif isinstance(event, ToolCallStart):
                        collected_tool_calls.append(event)
                        yield event

                    elif isinstance(event, TurnComplete):
                        last_usage = event.usage
                        last_finish_reason = event.finish_reason
            except Exception as e:
                yield TextChunk(text=f"\n[API Error: {e}]\n")
                yield TurnComplete(finish_reason="error", usage=TokenUsage(0, 0, 0))
                return

            # ── Record assistant message ───────────────────────────────────────
            tool_use_blocks = [
                ToolUseBlock(
                    tool_use_id=tc.tool_use_id,
                    tool_name=tc.tool_name,
                    params=tc.params,
                )
                for tc in collected_tool_calls
            ]
            self.messages.append(
                AssistantMessage(
                    content=collected_text,
                    tool_calls=tool_use_blocks,
                )
            )

            # ── No tool calls or non-tool_use finish: end turn ─────────────────
            if not collected_tool_calls or last_finish_reason != "tool_use":
                yield TurnComplete(finish_reason=last_finish_reason, usage=last_usage)
                return

            # ── Permission checks ──────────────────────────────────────────────
            permitted_calls: list[dict] = []

            for tc in collected_tool_calls:
                perm = check_permission(
                    tool_name=tc.tool_name,
                    params=tc.params,
                    mode=self.config.mode,
                    rules=self.config.rules,
                    auto_approved=self.auto_approved,
                )

                if perm.action == "deny":
                    error_msg = f"Permission denied: {perm.reason}"
                    self.messages.append(
                        ToolResultMessage(
                            tool_use_id=tc.tool_use_id,
                            content=error_msg,
                            is_error=True,
                        )
                    )
                    yield ToolCallResult(
                        tool_use_id=tc.tool_use_id,
                        result=error_msg,
                        is_error=True,
                    )
                    continue

                if perm.action == "ask" and self.confirm_fn is not None:
                    while True:
                        response = self.confirm_fn(tc.tool_name, tc.params)
                        answer = await response if hasattr(response, "__await__") else response
                        answer = answer.strip().lower()
                        if answer != "h":
                            break
                        helmet = await self._safety_engine.helmet_review(
                            tc.tool_name,
                            tc.params,
                            self.messages,
                            provider=self._reviewer_provider,
                        )
                        if helmet is not None:
                            yield HelmetReviewResult(
                                tool_name=tc.tool_name,
                                severity=helmet["severity"],
                                summary=helmet["summary"],
                                expected_effect=helmet["expected_effect"],
                                recommendation=helmet["recommendation"],
                            )
                    if answer == "a":
                        # Auto-approve this tool for the rest of the session
                        self.auto_approved[tc.tool_name] = True
                        permitted_calls.append(
                            {
                                "tool_name": tc.tool_name,
                                "tool_use_id": tc.tool_use_id,
                                "params": tc.params,
                            }
                        )
                    elif answer == "y":
                        permitted_calls.append(
                            {
                                "tool_name": tc.tool_name,
                                "tool_use_id": tc.tool_use_id,
                                "params": tc.params,
                            }
                        )
                    else:
                        # User denied
                        error_msg = "User denied tool execution."
                        self.messages.append(
                            ToolResultMessage(
                                tool_use_id=tc.tool_use_id,
                                content=error_msg,
                                is_error=True,
                            )
                        )
                        yield ToolCallResult(
                            tool_use_id=tc.tool_use_id,
                            result=error_msg,
                            is_error=True,
                        )
                else:
                    # allow (or run ask without confirm_fn)
                    review = await self._safety_engine.review(
                        tc.tool_name,
                        tc.params,
                        self.messages[-6:],
                        provider=self._reviewer_provider,
                    )
                    if review.should_pause and not self.safety_auto_approved.get(tc.tool_name):
                        yield SafetyAlert(
                            tool_name=tc.tool_name,
                            severity=review.severity,
                            reason=review.reason,
                            params=tc.params,
                            review_source=review.source,
                            review_activity=review.reviewer_note,
                        )
                        answer = "n"
                        if self.safety_confirm_fn is not None:
                            while True:
                                response = self.safety_confirm_fn(review)
                                answer = await response if hasattr(response, "__await__") else response
                                answer = str(answer).strip().lower()
                                if answer != "h":
                                    break
                                helmet = await self._safety_engine.helmet_review(
                                    tc.tool_name,
                                    tc.params,
                                    self.messages,
                                    provider=self._reviewer_provider,
                                )
                                if helmet is not None:
                                    yield HelmetReviewResult(
                                        tool_name=tc.tool_name,
                                        severity=helmet["severity"],
                                        summary=helmet["summary"],
                                        expected_effect=helmet["expected_effect"],
                                        recommendation=helmet["recommendation"],
                                    )
                        if answer == "a":
                            self.safety_auto_approved[tc.tool_name] = True
                        elif answer != "y":
                            error_msg = f"Safety review blocked execution: {review.reason}"
                            self.messages.append(
                                ToolResultMessage(
                                    tool_use_id=tc.tool_use_id,
                                    content=error_msg,
                                    is_error=True,
                                )
                            )
                            yield ToolCallResult(
                                tool_use_id=tc.tool_use_id,
                                result=error_msg,
                                is_error=True,
                            )
                            continue

                    permitted_calls.append(
                        {
                            "tool_name": tc.tool_name,
                            "tool_use_id": tc.tool_use_id,
                            "params": tc.params,
                        }
                    )

            # ── Execute permitted tool calls ───────────────────────────────────
            if permitted_calls:
                results = await run_tool_calls(permitted_calls, ctx)
                for call in permitted_calls:
                    tid = call["tool_use_id"]
                    tool_result = results[tid]
                    self.messages.append(
                        ToolResultMessage(
                            tool_use_id=tid,
                            content=tool_result.output,
                            is_error=tool_result.is_error,
                        )
                    )
                    yield ToolCallResult(
                        tool_use_id=tid,
                        result=tool_result.output,
                        is_error=tool_result.is_error,
                    )

            # Continue loop: model sees tool results and produces next reply

        # Exceeded max_turns
        yield TurnComplete(
            finish_reason="max_turns",
            usage=last_usage,
        )

    @staticmethod
    def _build_provider_kwargs(config_like: Any) -> dict[str, Any]:
        provider_kwargs: dict[str, Any] = {}
        if getattr(config_like, "api_key", ""):
            provider_kwargs["api_key"] = config_like.api_key
        if getattr(config_like, "base_url", ""):
            provider_kwargs["base_url"] = config_like.base_url
        if getattr(config_like, "auth_token", ""):
            provider_kwargs["auth_token"] = config_like.auth_token
        if getattr(config_like, "azure_endpoint", ""):
            provider_kwargs["azure_endpoint"] = config_like.azure_endpoint
            provider_kwargs["azure_api_version"] = getattr(config_like, "azure_api_version", "2024-02-01")
        return provider_kwargs
