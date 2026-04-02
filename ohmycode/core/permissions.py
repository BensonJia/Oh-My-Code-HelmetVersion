"""Permission pipeline: input validation → rule matching → mode checks → user confirmation."""
from __future__ import annotations
import fnmatch
import re
from dataclasses import dataclass
from typing import Any

DANGEROUS_TOOLS = {"bash", "edit", "write", "agent"}
PLAN_BLOCKED_TOOLS = {"bash", "edit", "write", "agent"}

@dataclass
class PermissionResult:
    action: str  # "allow" | "deny" | "ask"
    reason: str = ""

def _match_pattern(value: str, pattern: str, match_type: str) -> bool:
    if match_type == "regex":
        return bool(re.search(pattern, value))
    else:
        return fnmatch.fnmatch(value, pattern)

def match_rules(tool_name: str, params: dict[str, Any], rules: list[dict[str, Any]]) -> str | None:
    matched_actions: list[str] = []
    for rule in rules:
        if rule.get("tool") != tool_name:
            continue
        match_field = rule.get("match_field")
        pattern = rule.get("pattern")
        if match_field and pattern:
            value = str(params.get(match_field, ""))
            match_type = rule.get("match_type", "glob")
            if not _match_pattern(value, pattern, match_type):
                continue
        matched_actions.append(rule.get("action", "ask"))
    if not matched_actions:
        return None
    if "deny" in matched_actions:
        return "deny"
    if "ask" in matched_actions:
        return "ask"
    return "allow"

def check_permission(tool_name: str, params: dict[str, Any], mode: str,
    rules: list[dict[str, Any]], auto_approved: dict[str, bool]) -> PermissionResult:
    rule_action = match_rules(tool_name, params, rules)
    if rule_action == "deny":
        return PermissionResult(action="deny", reason="Blocked by rule")
    if rule_action == "allow":
        return PermissionResult(action="allow", reason="Allowed by rule")
    if mode == "plan" and tool_name in PLAN_BLOCKED_TOOLS:
        return PermissionResult(action="deny", reason=f"Plan mode: {tool_name} is not allowed")
    if mode == "auto":
        return PermissionResult(action="allow", reason="Auto mode")
    if auto_approved.get(tool_name):
        return PermissionResult(action="allow", reason="Auto-approved for this session")
    if mode == "default" and tool_name in DANGEROUS_TOOLS:
        return PermissionResult(action="ask", reason=f"{tool_name} requires user confirmation")
    return PermissionResult(action="allow", reason="Safe tool")
