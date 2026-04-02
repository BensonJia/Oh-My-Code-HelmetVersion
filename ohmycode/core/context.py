"""Four-level context compression and circuit breaker (Task 16)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List

import tiktoken

from ohmycode.core.messages import AssistantMessage, Message, UserMessage

if TYPE_CHECKING:
    pass

# Overhead tokens per message (role token + separators, approximation)
_MSG_OVERHEAD = 4
_ENCODING = None


def _get_encoding() -> tiktoken.Encoding:
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def _count_text_tokens(text: str) -> int:
    enc = _get_encoding()
    return len(enc.encode(text))


class ContextManager:
    """Manages context window usage with four compression levels and a circuit breaker."""

    def __init__(self, token_budget: int, output_reserved: int) -> None:
        self.token_budget = token_budget
        self.output_reserved = output_reserved
        # Circuit breaker state
        self._failure_count = 0
        self._max_failures = 3

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count_tokens(self, messages: List[Message], system_prompt: str = "") -> int:
        """Approximate token count for messages + system prompt."""
        total = 0
        if system_prompt:
            total += _count_text_tokens(system_prompt) + _MSG_OVERHEAD
        for msg in messages:
            content = getattr(msg, "content", "") or ""
            total += _count_text_tokens(content) + _MSG_OVERHEAD
        return total

    def get_usage_ratio(self, messages: List[Message], system_prompt: str = "") -> float:
        """Return token usage as fraction of effective window (budget - output_reserved)."""
        effective = max(1, self.token_budget - self.output_reserved)
        used = self.count_tokens(messages, system_prompt)
        return used / effective

    # ------------------------------------------------------------------
    # Level 1: snip — remove oldest 2–4 messages
    # ------------------------------------------------------------------

    def snip(self, messages: List[Message]) -> List[Message]:
        """Remove the 2–4 oldest messages."""
        if len(messages) <= 2:
            # Can't meaningfully snip fewer than 2 messages
            return list(messages)
        remove = min(4, max(2, len(messages) // 4))
        # Round down to even number to keep user/assistant pairs
        if remove % 2 != 0:
            remove -= 1
        remove = max(2, remove)
        return list(messages[remove:])

    # ------------------------------------------------------------------
    # Circuit breaker helper
    # ------------------------------------------------------------------

    def _check_circuit_breaker(self) -> None:
        if self._failure_count >= self._max_failures:
            raise RuntimeError(
                f"Circuit breaker open: {self._failure_count} consecutive LLM failures. "
                "Compression is unavailable."
            )

    def _record_failure(self) -> None:
        self._failure_count += 1

    def _record_success(self) -> None:
        self._failure_count = 0

    # ------------------------------------------------------------------
    # Level 2: micro_compact — summarize oldest 20%
    # ------------------------------------------------------------------

    async def micro_compact(
        self, messages: List[Message], provider, model: str
    ) -> List[Message]:
        """Summarize oldest 20% of messages with an LLM call."""
        self._check_circuit_breaker()
        if len(messages) < 4:
            # Still attempt the LLM call so circuit breaker counts failures
            # but with the full message list as context
            old_text = "\n".join(
                f"{getattr(m, 'role', 'user')}: {getattr(m, 'content', '')}" for m in messages
            )
            prompt = f"Summarize the following conversation excerpt in 1-2 sentences:\n\n{old_text}"
            try:
                summary = await self._llm_summarize(provider, model, prompt)
                self._record_success()
            except Exception:
                self._record_failure()
                raise
            return list(messages)
        split = max(2, len(messages) // 5)
        old = messages[:split]
        recent = messages[split:]
        old_text = "\n".join(
            f"{getattr(m, 'role', 'user')}: {getattr(m, 'content', '')}" for m in old
        )
        prompt = (
            f"Summarize the following conversation excerpt in 1-2 sentences:\n\n{old_text}"
        )
        try:
            summary = await self._llm_summarize(provider, model, prompt)
            self._record_success()
        except Exception as exc:
            self._record_failure()
            raise
        summary_msg = UserMessage(content=f"[Earlier context summary]: {summary}")
        return [summary_msg] + list(recent)

    # ------------------------------------------------------------------
    # Level 3: collapse — keep recent 20, summarize rest
    # ------------------------------------------------------------------

    async def collapse(
        self, messages: List[Message], provider, model: str
    ) -> List[Message]:
        """Keep the most recent 20 messages; summarize the rest."""
        self._check_circuit_breaker()
        keep = 20
        if len(messages) <= keep:
            return list(messages)
        old = messages[:-keep]
        recent = messages[-keep:]
        old_text = "\n".join(
            f"{getattr(m, 'role', 'user')}: {getattr(m, 'content', '')}" for m in old
        )
        prompt = (
            f"Summarize the following conversation in 2-3 sentences:\n\n{old_text}"
        )
        try:
            summary = await self._llm_summarize(provider, model, prompt)
            self._record_success()
        except Exception as exc:
            self._record_failure()
            raise
        summary_msg = UserMessage(content=f"[Conversation summary]: {summary}")
        return [summary_msg] + list(recent)

    # ------------------------------------------------------------------
    # Level 4: auto_compact — keep recent 10, one paragraph summary
    # ------------------------------------------------------------------

    async def auto_compact(
        self, messages: List[Message], provider, model: str
    ) -> List[Message]:
        """Keep the most recent 10 messages; summarize all else into one paragraph."""
        self._check_circuit_breaker()
        keep = 10
        if len(messages) <= keep:
            return list(messages)
        old = messages[:-keep]
        recent = messages[-keep:]
        old_text = "\n".join(
            f"{getattr(m, 'role', 'user')}: {getattr(m, 'content', '')}" for m in old
        )
        prompt = (
            "Write a single concise paragraph summarizing the key context "
            f"from this conversation:\n\n{old_text}"
        )
        try:
            summary = await self._llm_summarize(provider, model, prompt)
            self._record_success()
        except Exception as exc:
            self._record_failure()
            raise
        summary_msg = UserMessage(content=f"[Full conversation summary]: {summary}")
        return [summary_msg] + list(recent)

    # ------------------------------------------------------------------
    # Orchestrator: maybe_compress
    # ------------------------------------------------------------------

    async def maybe_compress(
        self,
        messages: List[Message],
        system_prompt: str,
        provider,
        model: str,
    ) -> List[Message]:
        """Check usage ratio and apply the appropriate compression strategy.

        Thresholds:
          75% → snip
          80% → micro_compact
          85% → collapse
          90% → auto_compact
        """
        ratio = self.get_usage_ratio(messages, system_prompt)
        if ratio < 0.75:
            return list(messages)
        if ratio < 0.80:
            return self.snip(messages)
        if ratio < 0.85:
            return await self.micro_compact(messages, provider, model)
        if ratio < 0.90:
            return await self.collapse(messages, provider, model)
        return await self.auto_compact(messages, provider, model)

    # ------------------------------------------------------------------
    # Internal LLM helper
    # ------------------------------------------------------------------

    async def _llm_summarize(self, provider, model: str, prompt: str) -> str:
        """Call the provider to produce a summary string."""
        from ohmycode.core.messages import AssistantMessage as AM, UserMessage as UM

        request_messages = [UM(content=prompt)]
        # provider.complete is expected to return an AssistantMessage or string
        result = await provider.complete(
            messages=request_messages,
            model=model,
            system_prompt="You are a helpful assistant that summarizes conversations.",
            tools=[],
        )
        if isinstance(result, str):
            return result
        if hasattr(result, "content"):
            return result.content
        return str(result)
