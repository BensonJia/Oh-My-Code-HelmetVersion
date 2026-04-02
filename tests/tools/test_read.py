"""Tests for ReadTool — read file contents with offset/limit."""

import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.read import ReadTool


class FakeRuntime:
    def __init__(self):
        self.paths = []

    async def read_file(self, file_path, offset=1, limit=None):
        self.paths.append((str(file_path), offset, limit))
        return type("ReadResult", (), {"output": "1\talpha\n2\tbeta\n", "is_error": False})()


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("alpha\nbeta\ngamma\ndelta\nepsilon\n")
    return str(f)


@pytest.mark.asyncio
async def test_read_entire_file(ctx, sample_file):
    tool = ReadTool()
    result = await tool.execute({"file_path": sample_file}, ctx)
    assert not result.is_error
    assert "1\talpha" in result.output
    assert "5\tepsilon" in result.output


@pytest.mark.asyncio
async def test_read_with_offset(ctx, sample_file):
    tool = ReadTool()
    result = await tool.execute({"file_path": sample_file, "offset": 3}, ctx)
    assert not result.is_error
    assert "3\tgamma" in result.output
    assert "alpha" not in result.output


@pytest.mark.asyncio
async def test_read_with_limit(ctx, sample_file):
    tool = ReadTool()
    result = await tool.execute({"file_path": sample_file, "limit": 2}, ctx)
    assert not result.is_error
    assert "2\tbeta" in result.output
    assert "gamma" not in result.output


@pytest.mark.asyncio
async def test_read_with_offset_and_limit(ctx, sample_file):
    tool = ReadTool()
    result = await tool.execute({"file_path": sample_file, "offset": 2, "limit": 2}, ctx)
    assert not result.is_error
    assert "2\tbeta" in result.output
    assert "3\tgamma" in result.output
    assert "delta" not in result.output


@pytest.mark.asyncio
async def test_read_file_not_found(ctx):
    tool = ReadTool()
    result = await tool.execute({"file_path": "/no/such/file.txt"}, ctx)
    assert result.is_error
    assert "escapes workspace" in result.output.lower()


@pytest.mark.asyncio
async def test_read_empty_file(ctx, tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")
    tool = ReadTool()
    result = await tool.execute({"file_path": str(f)}, ctx)
    assert not result.is_error
    assert result.output == ""


@pytest.mark.asyncio
async def test_read_uses_runtime(tmp_path, sample_file):
    ctx = ToolContext(
        mode="auto",
        agent_depth=0,
        cwd=str(tmp_path),
        is_sub_agent=False,
        runtime=FakeRuntime(),
    )
    tool = ReadTool()
    result = await tool.execute({"file_path": sample_file}, ctx)
    assert not result.is_error
    assert ctx.runtime.paths == [(sample_file, 1, None)]
