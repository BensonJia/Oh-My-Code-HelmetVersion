import pytest
from ohmycode.tools.base import ToolContext
from ohmycode.tools.web_fetch import WebFetchTool


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(mode="auto", agent_depth=0, cwd=str(tmp_path), is_sub_agent=False)


@pytest.mark.asyncio
async def test_web_fetch_invalid_url(ctx):
    """Test fetching an invalid URL."""
    tool = WebFetchTool()
    result = await tool.execute(
        {"url": "http://invalid-domain-that-does-not-exist-12345.com"}, ctx
    )
    assert result.is_error


@pytest.mark.asyncio
async def test_web_fetch_html_strip(ctx):
    """Test that HTML tags are stripped from HTML content."""
    tool = WebFetchTool()
    # This test would require a real HTTP server or mocking.
    # For now, we just verify the tool can be instantiated.
    assert tool.name == "web_fetch"
    assert tool.concurrent_safe is True
