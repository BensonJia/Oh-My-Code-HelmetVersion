import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.edit import EditTool


class FakeRuntime:
    def __init__(self, is_error=False, output="Replaced"):
        self.calls = []
        self.is_error = is_error
        self.output = output

    async def edit_file(self, file_path, old_string, new_string):
        self.calls.append((str(file_path), old_string, new_string))
        return type("EditResult", (), {"output": self.output, "is_error": self.is_error})()

@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)

@pytest.mark.asyncio
async def test_edit_replace(ctx, tmp_path):
    f = tmp_path / "test.py"
    f.write_text("hello world\nfoo bar\n")
    tool = EditTool()
    result = await tool.execute(
        {"file_path": str(f), "old_string": "hello world", "new_string": "goodbye world"}, ctx)
    assert not result.is_error
    assert f.read_text() == "goodbye world\nfoo bar\n"

@pytest.mark.asyncio
async def test_edit_old_string_not_unique(ctx, tmp_path):
    f = tmp_path / "test.py"
    f.write_text("aaa\naaa\n")
    tool = EditTool()
    result = await tool.execute(
        {"file_path": str(f), "old_string": "aaa", "new_string": "bbb"}, ctx)
    assert result.is_error

@pytest.mark.asyncio
async def test_edit_old_string_not_found(ctx, tmp_path):
    f = tmp_path / "test.py"
    f.write_text("hello world\n")
    tool = EditTool()
    result = await tool.execute(
        {"file_path": str(f), "old_string": "xyz", "new_string": "abc"}, ctx)
    assert result.is_error


@pytest.mark.asyncio
async def test_edit_uses_runtime(tmp_path):
    ctx = ToolContext(
        mode="auto",
        agent_depth=0,
        cwd=str(tmp_path),
        is_sub_agent=False,
        runtime=FakeRuntime(),
    )
    f = tmp_path / "test.py"
    tool = EditTool()
    result = await tool.execute(
        {"file_path": str(f), "old_string": "hello world", "new_string": "goodbye world"}, ctx)
    assert not result.is_error
    assert ctx.runtime.calls == [(str(f), "hello world", "goodbye world")]
