import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.web_search import WebSearchTool


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)


@pytest.mark.asyncio
async def test_web_search_tool_properties(ctx):
    """Test that WebSearchTool has correct properties."""
    tool = WebSearchTool()
    assert tool.name == "web_search"
    assert tool.concurrent_safe is True
    assert "query" in tool.parameters["properties"]
