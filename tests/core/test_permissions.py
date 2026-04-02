"""Tests for the permission pipeline."""
import pytest
from ohmycode.core.permissions import PermissionResult, check_permission, match_rules

def test_safe_tool_always_allowed():
    result = check_permission(tool_name="read", params={"file_path": "/tmp/test.py"},
        mode="default", rules=[], auto_approved={})
    assert result.action == "allow"

def test_dangerous_tool_needs_ask_in_default():
    result = check_permission(tool_name="bash", params={"command": "ls"},
        mode="default", rules=[], auto_approved={})
    assert result.action == "ask"

def test_auto_mode_allows_everything():
    result = check_permission(tool_name="bash", params={"command": "rm -rf /"},
        mode="auto", rules=[], auto_approved={})
    assert result.action == "allow"

def test_plan_mode_denies_writes():
    result = check_permission(tool_name="bash", params={"command": "ls"},
        mode="plan", rules=[], auto_approved={})
    assert result.action == "deny"

def test_plan_mode_allows_reads():
    result = check_permission(tool_name="read", params={"file_path": "/tmp/test"},
        mode="plan", rules=[], auto_approved={})
    assert result.action == "allow"

def test_deny_rule_overrides_mode():
    rules = [{"tool": "bash", "match_field": "command", "pattern": "rm*", "match_type": "glob", "action": "deny"}]
    result = check_permission(tool_name="bash", params={"command": "rm -rf /"},
        mode="auto", rules=rules, auto_approved={})
    assert result.action == "deny"

def test_allow_rule():
    rules = [{"tool": "bash", "action": "allow"}]
    result = check_permission(tool_name="bash", params={"command": "ls"},
        mode="default", rules=rules, auto_approved={})
    assert result.action == "allow"

def test_auto_approved_skips_ask():
    result = check_permission(tool_name="bash", params={"command": "ls"},
        mode="default", rules=[], auto_approved={"bash": True})
    assert result.action == "allow"

def test_deny_beats_allow_in_rules():
    rules = [
        {"tool": "bash", "action": "allow"},
        {"tool": "bash", "match_field": "command", "pattern": "rm*", "match_type": "glob", "action": "deny"},
    ]
    result = check_permission(tool_name="bash", params={"command": "rm -rf /"},
        mode="auto", rules=rules, auto_approved={})
    assert result.action == "deny"
