import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.write import WriteTool


class FakeRuntime:
    def __init__(self):
        self.calls = []

    async def write_file(self, file_path, content):
        self.calls.append((str(file_path), content))
        return type("WriteResult", (), {
            "output": f"Wrote {len(content)} characters to {file_path}",
            "is_error": False,
            "metadata": {"chars_written": len(content)},
        })()


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)


@pytest.mark.asyncio
async def test_write_new_file(ctx, tmp_path):
    f = tmp_path / "test.txt"
    tool = WriteTool()
    result = await tool.execute(
        {"file_path": str(f), "content": "hello world"}, ctx
    )
    assert not result.is_error
    assert f.read_text() == "hello world"
    assert result.metadata["chars_written"] == 11


@pytest.mark.asyncio
async def test_write_creates_parents(ctx, tmp_path):
    f = tmp_path / "a" / "b" / "c" / "test.txt"
    tool = WriteTool()
    result = await tool.execute(
        {"file_path": str(f), "content": "nested"}, ctx
    )
    assert not result.is_error
    assert f.read_text() == "nested"


@pytest.mark.asyncio
async def test_write_overwrite(ctx, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("old content")
    tool = WriteTool()
    result = await tool.execute(
        {"file_path": str(f), "content": "new content"}, ctx
    )
    assert not result.is_error
    assert f.read_text() == "new content"


@pytest.mark.asyncio
async def test_write_uses_runtime(tmp_path):
    ctx = ToolContext(
        mode="auto",
        agent_depth=0,
        cwd=str(tmp_path),
        is_sub_agent=False,
        runtime=FakeRuntime(),
    )
    f = tmp_path / "test.txt"
    tool = WriteTool()
    result = await tool.execute({"file_path": str(f), "content": "hello world"}, ctx)
    assert not result.is_error
    assert ctx.runtime.calls == [(str(f), "hello world")]
