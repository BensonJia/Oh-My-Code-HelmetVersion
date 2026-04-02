"""Tests for GrepTool — regex search over files."""

import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.grep import GrepTool


class FakeRuntime:
    def __init__(self):
        self.calls = []

    async def grep_search(self, pattern, path=None, glob_pat="**/*", case_insensitive=False):
        self.calls.append((pattern, path, glob_pat, case_insensitive))
        return type("GrepResult", (), {"output": "/workspace/code.py:1:def hello():", "is_error": False, "metadata": {}})()


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)


@pytest.fixture
def searchable(tmp_path):
    (tmp_path / "code.py").write_text("def hello():\n    return 'world'\n")
    (tmp_path / "notes.md").write_text("Hello World\nfoo bar\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("import hello\n")
    return tmp_path


@pytest.mark.asyncio
async def test_grep_basic(ctx, searchable):
    tool = GrepTool()
    result = await tool.execute({"pattern": "hello"}, ctx)
    assert not result.is_error
    assert "code.py" in result.output
    assert "def hello" in result.output


@pytest.mark.asyncio
async def test_grep_case_insensitive(ctx, searchable):
    tool = GrepTool()
    result = await tool.execute({"pattern": "hello", "-i": True}, ctx)
    assert not result.is_error
    # Should match "Hello" in notes.md too
    assert "notes.md" in result.output


@pytest.mark.asyncio
async def test_grep_glob_filter(ctx, searchable):
    tool = GrepTool()
    result = await tool.execute({"pattern": "hello", "glob": "*.py"}, ctx)
    assert not result.is_error
    assert "code.py" in result.output
    assert "notes.md" not in result.output


@pytest.mark.asyncio
async def test_grep_single_file(ctx, searchable):
    tool = GrepTool()
    target = str(searchable / "notes.md")
    result = await tool.execute({"pattern": "foo", "path": target}, ctx)
    assert not result.is_error
    assert "foo bar" in result.output


@pytest.mark.asyncio
async def test_grep_no_matches(ctx, searchable):
    tool = GrepTool()
    result = await tool.execute({"pattern": "zzzzz_no_match"}, ctx)
    assert not result.is_error
    assert "No matches" in result.output


@pytest.mark.asyncio
async def test_grep_invalid_regex(ctx):
    tool = GrepTool()
    result = await tool.execute({"pattern": "[invalid"}, ctx)
    assert result.is_error
    assert "Invalid regex" in result.output


@pytest.mark.asyncio
async def test_grep_line_numbers(ctx, searchable):
    tool = GrepTool()
    result = await tool.execute({"pattern": "return"}, ctx)
    assert not result.is_error
    # "return" is on line 2 of code.py
    assert ":2:" in result.output


@pytest.mark.asyncio
async def test_grep_uses_runtime(tmp_path):
    ctx = ToolContext(
        mode="auto",
        agent_depth=0,
        cwd=str(tmp_path),
        is_sub_agent=False,
        runtime=FakeRuntime(),
    )
    tool = GrepTool()
    result = await tool.execute({"pattern": "hello", "-i": True}, ctx)
    assert not result.is_error
    assert ctx.runtime.calls == [("hello", str(tmp_path), "**/*", True)]
