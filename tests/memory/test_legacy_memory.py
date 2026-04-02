"""Tests for legacy memory wrappers and helper functions."""

from __future__ import annotations

import pytest

import ohmycode.memory.memory as mem_mod
from ohmycode.memory.memory import (
    _parse_frontmatter_meta,
    delete_memory,
    list_memories,
    load_memory_index,
    save_memory,
)


@pytest.fixture(autouse=True)
def isolate_memory_dir(tmp_path, monkeypatch):
    """Redirect MEMORY_DIR and MEMORY_INDEX to tmp_path."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    monkeypatch.setattr(mem_mod, "MEMORY_DIR", memory_dir)
    monkeypatch.setattr(mem_mod, "MEMORY_INDEX", memory_dir / "MEMORY.md")
    return memory_dir


# ---- _parse_frontmatter_meta ----

def test_parse_frontmatter_happy():
    content = "---\nname: My Memory\ntype: user\ncreated: 20250101\n---\n\nBody text."
    name, mem_type = _parse_frontmatter_meta(content)
    assert name == "My Memory"
    assert mem_type == "user"


def test_parse_frontmatter_no_frontmatter():
    name, mem_type = _parse_frontmatter_meta("Just plain text")
    assert name == "unknown"
    assert mem_type == "general"


def test_parse_frontmatter_partial():
    content = "---\nname: Partial\n---\nBody"
    name, mem_type = _parse_frontmatter_meta(content)
    assert name == "Partial"
    assert mem_type == "general"


# ---- save_memory ----

def test_save_memory_creates_file(isolate_memory_dir):
    filename = save_memory("test_mem", "user", "Some content")
    assert filename.endswith(".md")
    assert (isolate_memory_dir / filename).exists()


def test_save_memory_updates_index(isolate_memory_dir):
    save_memory("my note", "project", "details")
    index = load_memory_index()
    assert "my note" in index


# ---- load_memory_index ----

def test_load_memory_index_empty(isolate_memory_dir):
    index = load_memory_index()
    assert index == ""


def test_load_memory_index_after_save(isolate_memory_dir):
    save_memory("alpha", "user", "content A")
    save_memory("beta", "feedback", "content B")
    index = load_memory_index()
    assert "alpha" in index
    assert "beta" in index


# ---- list_memories ----

def test_list_memories_empty(isolate_memory_dir):
    assert list_memories() == []


def test_list_memories_returns_saved(isolate_memory_dir):
    save_memory("mem1", "user", "body1")
    save_memory("mem2", "reference", "body2")
    result = list_memories()
    names = [m["name"] for m in result]
    assert "mem1" in names
    assert "mem2" in names


# ---- delete_memory ----

def test_delete_memory_success(isolate_memory_dir):
    filename = save_memory("to_delete", "user", "bye")
    assert delete_memory(filename) is True
    assert not (isolate_memory_dir / filename).exists()


def test_delete_memory_nonexistent(isolate_memory_dir):
    assert delete_memory("no_such_file.md") is False


def test_delete_memory_updates_index(isolate_memory_dir):
    filename = save_memory("removable", "user", "temp")
    delete_memory(filename)
    index = load_memory_index()
    assert "removable" not in index
