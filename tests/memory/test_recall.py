"""Tests for keyword-based memory recall (Phase 3)."""

from pathlib import Path

import pytest

from ohmycode.memory.memory import BTreeMemoryStore
from ohmycode.memory.recall import RecallEngine


@pytest.fixture
def populated_store(tmp_path):
    """A BTreeMemoryStore pre-loaded with diverse memories."""
    store = BTreeMemoryStore(tmp_path / "memory")
    store.ensure_tree()
    store.save("senior-engineer", "user", "User is a senior backend engineer with 10 years Go experience")
    store.save("prefers-terse", "user", "User prefers terse responses, no trailing summaries")
    store.save("no-mock-db", "feedback", "Integration tests must use real database, never mocks")
    store.save("bundled-prs", "feedback", "Prefer single bundled PR for refactors over many small ones")
    store.save("use-bun", "feedback", "Use bun instead of npm for package management")
    store.save("auth-rewrite", "project", "Auth middleware rewrite driven by legal compliance, deadline March 15")
    store.save("merge-freeze", "project", "Merge freeze starting March 5 for mobile release branch cut")
    store.save("pipeline-linear", "reference", "Pipeline bugs tracked in Linear project INGEST")
    store.save("grafana-dashboard", "reference", "Oncall latency dashboard at grafana.internal/d/api-latency")
    return store


class TestRecallEngine:
    """RecallEngine selects relevant categories based on keywords."""

    def test_init(self, populated_store):
        engine = RecallEngine(populated_store)
        assert engine is not None

    def test_select_categories_returns_list(self, populated_store):
        engine = RecallEngine(populated_store)
        cats = engine.select_categories("what testing rules do we have?")
        assert isinstance(cats, list)

    def test_testing_query_selects_feedback(self, populated_store):
        engine = RecallEngine(populated_store)
        cats = engine.select_categories("what testing rules do we have?")
        assert "feedback" in cats

    def test_auth_query_selects_project(self, populated_store):
        engine = RecallEngine(populated_store)
        cats = engine.select_categories("tell me about the auth rewrite deadline")
        assert "project" in cats

    def test_dashboard_query_selects_reference(self, populated_store):
        engine = RecallEngine(populated_store)
        cats = engine.select_categories("where is the monitoring dashboard?")
        assert "reference" in cats

    def test_user_profile_query_selects_user(self, populated_store):
        engine = RecallEngine(populated_store)
        cats = engine.select_categories("what is my background and experience?")
        assert "user" in cats

    def test_max_categories_is_bounded(self, populated_store):
        engine = RecallEngine(populated_store)
        cats = engine.select_categories("everything about testing auth dashboards and my profile")
        assert len(cats) <= 3


class TestRecallOutput:
    """recall() returns root index + relevant summaries."""

    def test_recall_always_includes_root(self, populated_store):
        engine = RecallEngine(populated_store)
        result = engine.recall("what testing rules do we have?")
        assert "Memory Index" in result

    def test_recall_includes_relevant_summary(self, populated_store):
        engine = RecallEngine(populated_store)
        result = engine.recall("what testing rules do we have?")
        assert "no-mock-db" in result

    def test_recall_empty_query_returns_root_only(self, populated_store):
        engine = RecallEngine(populated_store)
        result = engine.recall("")
        assert "Memory Index" in result

    def test_recall_irrelevant_query_returns_root(self, populated_store):
        engine = RecallEngine(populated_store)
        result = engine.recall("what is the weather today?")
        assert "Memory Index" in result


class TestStaleness:
    """Staleness caveats on category summaries."""

    def test_fresh_memory_no_caveat(self, populated_store):
        engine = RecallEngine(populated_store)
        result = engine.recall("testing rules")
        assert "days old" not in result or "0 days" not in result
