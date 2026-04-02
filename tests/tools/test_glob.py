"""Tests for GlobTool — file pattern matching."""

import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.glob_tool import GlobTool


class FakeRuntime:
    def __init__(self):
        self.calls = []

    async def glob_search(self, pattern, path=None):
        self.calls.append((pattern, path))
        return type("GlobResult", (), {"output": "/workspace/a.py", "is_error": False, "metadata": {}})()


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)


@pytest.fixture
def file_tree(tmp_path):
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("c")
    (tmp_path / "readme.md").write_text("md")
    return tmp_path


@pytest.mark.asyncio
async def test_glob_star_py(ctx, file_tree):
    tool = GlobTool()
    result = await tool.execute({"pattern": "*.py"}, ctx)
    assert not result.is_error
    assert "a.py" in result.output
    assert "b.py" in result.output
    # non-recursive, so sub/c.py should NOT appear
    assert "c.py" not in result.output


@pytest.mark.asyncio
async def test_glob_recursive(ctx, file_tree):
    tool = GlobTool()
    result = await tool.execute({"pattern": "**/*.py"}, ctx)
    assert not result.is_error
    assert "c.py" in result.output


@pytest.mark.asyncio
async def test_glob_custom_path(file_tree):
    ctx = ToolContext(mode="auto", agent_depth=0, cwd="/tmp", is_sub_agent=False)
    tool = GlobTool()
    result = await tool.execute({"pattern": "*.py", "path": str(file_tree)}, ctx)
    assert result.is_error
    assert "escapes workspace" in result.output.lower()


@pytest.mark.asyncio
async def test_glob_no_match(ctx):
    tool = GlobTool()
    result = await tool.execute({"pattern": "*.xyz"}, ctx)
    assert not result.is_error
    assert "No files matched" in result.output


@pytest.mark.asyncio
async def test_glob_max_results(ctx, tmp_path):
    """Create 210 files, verify truncation at 200."""
    for i in range(210):
        (tmp_path / f"f{i:04d}.txt").write_text("")
    tool = GlobTool()
    result = await tool.execute({"pattern": "*.txt"}, ctx)
    assert not result.is_error
    lines = result.output.strip().split("\n")
    assert len(lines) == 200


@pytest.mark.asyncio
async def test_glob_uses_runtime(tmp_path):
    ctx = ToolContext(
        mode="auto",
        agent_depth=0,
        cwd=str(tmp_path),
        is_sub_agent=False,
        runtime=FakeRuntime(),
    )
    tool = GlobTool()
    result = await tool.execute({"pattern": "*.py"}, ctx)
    assert not result.is_error
    assert ctx.runtime.calls == [("*.py", str(tmp_path))]
