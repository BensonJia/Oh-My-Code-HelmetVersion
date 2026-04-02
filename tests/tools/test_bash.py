import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.bash import BashTool


class FakeRuntime:
    def __init__(self):
        self.calls = []

    async def exec(self, command, timeout=None):
        self.calls.append((command, timeout))
        return type("ExecResult", (), {"output": "hello\n", "is_error": False})()

@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)

@pytest.mark.asyncio
async def test_bash_echo(ctx):
    tool = BashTool()
    result = await tool.execute({"command": "echo hello"}, ctx)
    assert result.output.strip() == "hello"
    assert not result.is_error

@pytest.mark.asyncio
async def test_bash_exit_code(ctx):
    tool = BashTool()
    result = await tool.execute({"command": "exit 1"}, ctx)
    assert result.is_error

@pytest.mark.asyncio
async def test_bash_timeout(ctx):
    tool = BashTool()
    result = await tool.execute({"command": 'python -c "import time; time.sleep(10)"', "timeout": 1}, ctx)
    assert result.is_error
    assert "timeout" in result.output.lower() or "timed out" in result.output.lower()


@pytest.mark.asyncio
async def test_bash_uses_runtime(tmp_path):
    ctx = ToolContext(
        mode="auto",
        agent_depth=0,
        cwd=str(tmp_path),
        is_sub_agent=False,
        runtime=FakeRuntime(),
    )
    tool = BashTool()
    result = await tool.execute({"command": "echo hello"}, ctx)
    assert not result.is_error
    assert ctx.runtime.calls == [("echo hello", 120)]
