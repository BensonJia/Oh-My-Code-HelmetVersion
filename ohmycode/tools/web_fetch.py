"""WebFetch tool — fetch URL content."""

from __future__ import annotations

import html
import re

import httpx

from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool


@register_tool
class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch a URL and return its body as text."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
        },
        "required": ["url"],
    }
    concurrent_safe = True

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        url = params["url"]

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()

            content = response.text

            # Check for HTML
            content_type = response.headers.get("content-type", "").lower()
            if "html" in content_type:
                content = self._strip_html_tags(content)

            # Truncate to 50000 characters
            if len(content) > 50000:
                content = content[:50000]

            return ToolResult(output=content, is_error=False)

        except httpx.RequestError as exc:
            return ToolResult(output=f"Network error: {exc}", is_error=True)
        except Exception as exc:
            return ToolResult(output=f"Error fetching URL: {exc}", is_error=True)

    def _strip_html_tags(self, text: str) -> str:
        """Strip HTML tags and script/style content."""
        # Remove script and style blocks
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        text = html.unescape(text)

        # Collapse extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text
