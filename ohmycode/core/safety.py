"""Deterministic pre-execution safety checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ohmycode.config.config import SafetyConfig


_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_CONFIDENCE_LEVELS = {"low", "medium", "high"}
_RECOMMENDED_ACTIONS = {"allow", "pause", "deny"}
_HELMET_RECOMMENDATIONS = {"allow", "pause", "deny"}


def build_llm_reviewer_system_prompt() -> str:
    return (
        "You are a lightweight safety reviewer for tool execution. "
        "Return JSON only. Do not add markdown. "
        "Required keys: severity, reason, suspicious, confidence, categories, evidence, recommended_action. "
        "severity must be one of: low, medium, high, critical. "
        "confidence must be one of: low, medium, high. "
        "recommended_action must be one of: allow, pause, deny. "
        "categories must be an array of short snake_case strings. "
        "evidence must be an array of short factual strings grounded in the tool call or recent messages. "
        "Use suspicious=true only when the combination of tool call and context suggests real risk. "
        "Escalate cautiously; this reviewer supplements deterministic rules and should avoid false positives."
    )


def build_llm_reviewer_payload(
    tool_name: str,
    params: dict,
    recent_messages: list,
    max_chars: int,
) -> str:
    history = []
    for msg in recent_messages[-6:]:
        role = getattr(msg, "role", "unknown")
        content = str(getattr(msg, "content", ""))[:500]
        history.append({"role": role, "content": content})

    payload = json.dumps(
        {
            "tool_name": tool_name,
            "params": params,
            "recent_messages": history,
            "task": (
                "Assess whether this tool call is contextually suspicious. "
                "Prefer low severity unless there is evidence of destructive action, secret access, privilege escalation, or exfiltration."
            ),
        },
        ensure_ascii=False,
    )
    return payload[:max_chars] if len(payload) > max_chars else payload


def build_helmet_system_prompt() -> str:
    return (
        "You are Helmet, a strict safety reviewer for tool execution. "
        "Return JSON only. Do not add markdown. "
        "Required keys: severity, summary, expected_effect, confidence, recommendation, evidence. "
        "severity must be one of: low, medium, high, critical. "
        "confidence must be one of: low, medium, high. "
        "recommendation must be one of: allow, pause, deny. "
        "expected_effect must describe what the command is likely to do if executed. "
        "evidence must be an array of short factual strings grounded in the full conversation or tool call."
    )


def build_helmet_payload(
    tool_name: str,
    params: dict,
    all_messages: list,
    max_chars: int,
) -> str:
    history = []
    for msg in all_messages:
        role = getattr(msg, "role", "unknown")
        content = str(getattr(msg, "content", ""))[:500]
        history.append({"role": role, "content": content})
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "params": params,
            "full_conversation": history,
            "task": (
                "Review the full conversation context, estimate the risk level, and explain the expected execution effect "
                "before the operator decides whether to continue."
            ),
        },
        ensure_ascii=False,
    )
    return payload[:max_chars] if len(payload) > max_chars else payload


@dataclass
class SafetyReview:
    tool_name: str
    severity: str
    reason: str
    should_pause: bool
    source: str = "rules"
    reviewer_used: bool = False
    reviewer_note: str = ""


class SafetyEngine:
    def __init__(self, config: SafetyConfig):
        self.config = config

    def review_sync(self, tool_name: str, params: dict, recent_messages: list) -> SafetyReview:
        if not self.config.enabled:
            return SafetyReview(
                tool_name=tool_name,
                severity="low",
                reason="Safety engine disabled",
                should_pause=False,
                source="rules",
            )

        severity = "low"
        reason = "No elevated risk detected."

        if tool_name == "bash":
            command = str(params.get("command", ""))
            for token in self.config.dangerous_commands:
                if token in command:
                    severity = "critical" if token == "rm -rf" else "high"
                    reason = f"Command contains dangerous pattern: {token}"
                    break
        elif tool_name in {"read", "write", "edit"}:
            path = str(params.get("file_path", ""))
            for marker in self.config.sensitive_paths:
                if marker in path:
                    severity = "high"
                    reason = f"Path targets sensitive material: {marker}"
                    break

        should_pause = _SEVERITY_ORDER[severity] >= _SEVERITY_ORDER.get(self.config.pause_on_severity, 1)
        return SafetyReview(
            tool_name=tool_name,
            severity=severity,
            reason=reason,
            should_pause=should_pause,
            source="rules",
        )

    async def review(
        self,
        tool_name: str,
        params: dict,
        recent_messages: list,
        provider: Any | None = None,
    ) -> SafetyReview:
        base_review = self.review_sync(tool_name, params, recent_messages)
        if not self._should_use_llm(base_review, provider):
            return base_review

        try:
            llm_review = await self._llm_review(tool_name, params, recent_messages, provider)
        except Exception:
            return base_review
        if llm_review is None:
            return base_review
        return self._merge_reviews(base_review, llm_review, tool_name)

    async def helmet_review(
        self,
        tool_name: str,
        params: dict,
        all_messages: list,
        provider: Any | None = None,
    ) -> dict[str, Any] | None:
        if not self._helmet_available(provider):
            return None
        prompt = build_helmet_payload(
            tool_name=tool_name,
            params=params,
            all_messages=all_messages,
            max_chars=self.config.llm_reviewer.max_chars,
        )
        try:
            result = await provider.complete(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.llm_reviewer.model,
                system_prompt=build_helmet_system_prompt(),
                tools=[],
            )
        except Exception:
            return None
        raw = result.content if hasattr(result, "content") else str(result)
        return parse_helmet_response(raw)

    def _should_use_llm(self, base_review: SafetyReview, provider: Any | None) -> bool:
        return (
            self.config.enabled
            and self.config.llm_reviewer.enabled
            and bool(self.config.llm_reviewer.model)
            and provider is not None
            and hasattr(provider, "complete")
            and _SEVERITY_ORDER.get(base_review.severity, 0) <= _SEVERITY_ORDER["medium"]
        )

    def _helmet_available(self, provider: Any | None) -> bool:
        return (
            self.config.enabled
            and self.config.llm_reviewer.enabled
            and bool(self.config.llm_reviewer.model)
            and provider is not None
            and hasattr(provider, "complete")
        )

    async def _llm_review(
        self,
        tool_name: str,
        params: dict,
        recent_messages: list,
        provider: Any,
    ) -> dict[str, Any] | None:
        prompt = build_llm_reviewer_payload(
            tool_name=tool_name,
            params=params,
            recent_messages=recent_messages,
            max_chars=self.config.llm_reviewer.max_chars,
        )

        result = await provider.complete(
            messages=[{"role": "user", "content": prompt}],
            model=self.config.llm_reviewer.model,
            system_prompt=build_llm_reviewer_system_prompt(),
            tools=[],
        )
        raw = result.content if hasattr(result, "content") else str(result)
        return parse_llm_reviewer_response(raw)

    def _merge_reviews(
        self,
        base_review: SafetyReview,
        llm_review: dict[str, Any],
        tool_name: str,
    ) -> SafetyReview:
        base_level = _SEVERITY_ORDER[base_review.severity]
        llm_level = _SEVERITY_ORDER[llm_review["severity"]]
        if not llm_review.get("suspicious") or llm_level <= base_level:
            return base_review
        severity = llm_review["severity"]
        should_pause = _SEVERITY_ORDER[severity] >= _SEVERITY_ORDER.get(self.config.pause_on_severity, 1)
        return SafetyReview(
            tool_name=tool_name,
            severity=severity,
            reason=llm_review["reason"],
            should_pause=should_pause,
            source="llm_reviewer",
            reviewer_used=True,
            reviewer_note=(
                "LLM reviewer analyzed contextual risk because deterministic rules were "
                "inconclusive or only low/medium severity."
            ),
        )


def parse_llm_reviewer_response(raw: str) -> dict[str, Any] | None:
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None

    severity = str(data.get("severity", "")).lower()
    confidence = str(data.get("confidence", "")).lower()
    recommended_action = str(data.get("recommended_action", "")).lower()
    reason = str(data.get("reason", "")).strip()
    suspicious = data.get("suspicious", False)
    categories = data.get("categories", [])
    evidence = data.get("evidence", [])

    if severity not in _SEVERITY_ORDER:
        return None
    if confidence not in _CONFIDENCE_LEVELS:
        return None
    if recommended_action not in _RECOMMENDED_ACTIONS:
        return None
    if not isinstance(suspicious, bool):
        return None
    if not reason:
        return None
    if not isinstance(categories, list) or not all(isinstance(item, str) and item.strip() for item in categories):
        return None
    if not isinstance(evidence, list) or not all(isinstance(item, str) and item.strip() for item in evidence):
        return None

    return {
        "severity": severity,
        "reason": reason,
        "suspicious": suspicious,
        "confidence": confidence,
        "categories": [item.strip() for item in categories],
        "evidence": [item.strip() for item in evidence],
        "recommended_action": recommended_action,
    }


def parse_helmet_response(raw: str) -> dict[str, Any] | None:
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None

    severity = str(data.get("severity", "")).lower()
    summary = str(data.get("summary", "")).strip()
    expected_effect = str(data.get("expected_effect", "")).strip()
    confidence = str(data.get("confidence", "")).lower()
    recommendation = str(data.get("recommendation", "")).lower()
    evidence = data.get("evidence", [])

    if severity not in _SEVERITY_ORDER:
        return None
    if confidence not in _CONFIDENCE_LEVELS:
        return None
    if recommendation not in _HELMET_RECOMMENDATIONS:
        return None
    if not summary or not expected_effect:
        return None
    if not isinstance(evidence, list) or not all(isinstance(item, str) and item.strip() for item in evidence):
        return None

    return {
        "severity": severity,
        "summary": summary,
        "expected_effect": expected_effect,
        "confidence": confidence,
        "recommendation": recommendation,
        "evidence": [item.strip() for item in evidence],
    }
