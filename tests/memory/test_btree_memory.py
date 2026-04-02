"""Tests for B+-Tree hierarchical memory system — Phase 1 & 2."""

import os
import re
from pathlib import Path

import pytest

from ohmycode.memory.memory import (
    BTreeMemoryStore,
    get_project_memory_dir,
    MAX_INDEX_LINES,
    MAX_INDEX_BYTES,
)


# ---- Phase 1: Foundation tests ----


class TestProjectMemoryDir:
    """get_project_memory_dir() scopes memory to git root."""

    def test_returns_path_under_ohmycode_projects(self, tmp_path):
        result = get_project_memory_dir(str(tmp_path))
        assert ".ohmycode" in str(result)
        assert "projects" in str(result)
        assert "memory" in str(result)

    def test_git_root_produces_stable_slug(self, tmp_path):
        """Same cwd always yields the same memory dir."""
        a = get_project_memory_dir(str(tmp_path))
        b = get_project_memory_dir(str(tmp_path))
        assert a == b

    def test_different_dirs_produce_different_slugs(self, tmp_path):
        dir_a = tmp_path / "project_a"
        dir_b = tmp_path / "project_b"
        dir_a.mkdir()
        dir_b.mkdir()
        assert get_project_memory_dir(str(dir_a)) != get_project_memory_dir(str(dir_b))

    def test_slug_is_filesystem_safe(self, tmp_path):
        result = get_project_memory_dir(str(tmp_path))
        slug = Path(result).parent.name  # the project slug part
        assert re.match(r'^[\w\-]+$', slug), f"Slug not filesystem-safe: {slug}"


class TestBTreeStoreInit:
    """BTreeMemoryStore creates the correct directory structure."""

    def test_ensure_tree_creates_category_dirs(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        for cat in ("user", "feedback", "project", "reference"):
            assert (tmp_path / "memory" / cat).is_dir()

    def test_ensure_tree_creates_index(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        assert (tmp_path / "memory" / "INDEX.md").exists()

    def test_idempotent(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        store.ensure_tree()  # should not raise


class TestFilenameCollision:
    """Filenames use millisecond + random suffix to avoid collisions."""

    def test_two_saves_get_different_filenames(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        f1 = store.save("fact-a", "user", "content a")
        f2 = store.save("fact-a", "user", "content b")
        assert f1 != f2

    def test_filename_has_timestamp_and_suffix(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        fname = store.save("my-fact", "user", "some content")
        assert re.match(r'^\d{17}_[a-z0-9]{4}_[\w\-]+\.md$', fname), \
            f"Unexpected filename format: {fname}"


# ---- Phase 1: Index caps ----


class TestIndexCaps:
    """INDEX.md is bounded by line and byte caps."""

    def test_max_index_lines_defined(self):
        assert MAX_INDEX_LINES == 30

    def test_max_index_bytes_defined(self):
        assert MAX_INDEX_BYTES == 4096

    def test_root_index_stays_under_line_cap(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        for i in range(50):
            store.save(f"fact-{i}", "user", f"content {i}")
        index_content = store.get_root_index()
        lines = [l for l in index_content.strip().splitlines() if l.strip()]
        assert len(lines) <= MAX_INDEX_LINES

    def test_root_index_stays_under_byte_cap(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        for i in range(50):
            store.save(f"fact-{i}", "feedback", f"content {i}")
        index_content = store.get_root_index()
        assert len(index_content.encode("utf-8")) <= MAX_INDEX_BYTES


# ---- Phase 2: CRUD operations ----


class TestBTreeCRUD:
    """Save, list, delete, read operations."""

    def test_save_creates_leaf_file(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        fname = store.save("my-pref", "user", "prefers dark mode")
        leaf_path = tmp_path / "memory" / "user" / fname
        assert leaf_path.exists()
        content = leaf_path.read_text(encoding="utf-8")
        assert "prefers dark mode" in content

    def test_save_updates_category_summary(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        store.save("my-pref", "user", "prefers dark mode")
        summary_path = tmp_path / "memory" / "user" / "_SUMMARY.md"
        assert summary_path.exists()
        content = summary_path.read_text(encoding="utf-8")
        assert "my-pref" in content

    def test_save_updates_root_index(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        store.save("my-pref", "user", "prefers dark mode")
        index = store.get_root_index()
        assert "user" in index
        assert "1" in index  # count should be 1

    def test_list_all(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        store.save("fact-a", "user", "content a")
        store.save("rule-b", "feedback", "content b")
        all_mems = store.list_all()
        assert len(all_mems) == 2

    def test_list_category(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        store.save("fact-a", "user", "content a")
        store.save("fact-b", "user", "content b")
        store.save("rule-c", "feedback", "content c")
        user_mems = store.list_category("user")
        assert len(user_mems) == 2

    def test_delete_removes_leaf(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        fname = store.save("temp", "project", "will be deleted")
        assert store.delete("project", fname)
        leaf_path = tmp_path / "memory" / "project" / fname
        assert not leaf_path.exists()

    def test_delete_updates_summary_and_index(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        fname = store.save("temp", "project", "will be deleted")
        store.delete("project", fname)
        summary = (tmp_path / "memory" / "project" / "_SUMMARY.md").read_text(encoding="utf-8")
        assert "temp" not in summary

    def test_delete_nonexistent_returns_false(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        assert not store.delete("user", "nonexistent.md")

    def test_read_leaf(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        fname = store.save("my-fact", "reference", "dashboard at grafana.internal")
        content = store.read_leaf("reference", fname)
        assert "grafana.internal" in content

    def test_invalid_category_raises(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        with pytest.raises(ValueError):
            store.save("bad", "invalid_type", "content")


# ---- Phase 2: Leaf frontmatter ----


class TestLeafFrontmatter:
    """Leaf files have proper YAML frontmatter."""

    def test_frontmatter_has_required_fields(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        fname = store.save("my-pref", "feedback", "no trailing summaries")
        leaf = (tmp_path / "memory" / "feedback" / fname).read_text(encoding="utf-8")
        assert leaf.startswith("---\n")
        assert "name: my-pref" in leaf
        assert "type: feedback" in leaf
        assert "created:" in leaf
        assert "---" in leaf[4:]  # closing frontmatter delimiter


# ---- Phase 2: Root index format ----


class TestRootIndexFormat:
    """INDEX.md is a compact one-line-per-category summary."""

    def test_empty_store_has_header(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        index = store.get_root_index()
        assert "Memory Index" in index

    def test_index_shows_category_counts(self, tmp_path):
        store = BTreeMemoryStore(tmp_path / "memory")
        store.ensure_tree()
        store.save("a", "user", "x")
        store.save("b", "user", "y")
        store.save("c", "feedback", "z")
        index = store.get_root_index()
        assert "user" in index and "2" in index
        assert "feedback" in index and "1" in index
