"""WebSearch tool — web search."""

from __future__ import annotations

import re

import httpx

from ohmycode.tools.base import Tool, ToolContext, ToolResult, register_tool


@register_tool
class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web and return the top 10 results."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
        },
        "required": ["query"],
    }
    concurrent_safe = True

    async def execute(self, params: dict, ctx: ToolContext) -> ToolResult:
        query = params["query"]

        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; OhMyCode/0.1)"},
            ) as client:
                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                )
                response.raise_for_status()

            html = response.text
            results = self._parse_results(html)

            if not results:
                return ToolResult(output="No results found.", is_error=False)

            # Format results
            formatted = "\n\n".join(
                f"**{r['title']}**\n{r['url']}\n{r['snippet']}" for r in results[:10]
            )

            return ToolResult(output=formatted, is_error=False)

        except httpx.RequestError as exc:
            return ToolResult(output=f"Network error: {exc}", is_error=True)
        except Exception as exc:
            return ToolResult(output=f"Error searching: {exc}", is_error=True)

    @staticmethod
    def _strip_tags(html_str: str) -> str:
        """Strip HTML tags."""
        return re.sub(r"<[^>]+>", "", html_str).strip()

    def _parse_results(self, html: str) -> list[dict]:
        """Parse DuckDuckGo HTML into result dicts."""
        results = []

        # Title + URL: result__a links (may include <b> tags)
        result_pattern = r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        # Snippet: result__snippet (may include <b> tags)
        snippet_pattern = r'class="result__snippet"[^>]*>(.*?)</(?:span|a)>'

        title_url_matches = list(re.finditer(result_pattern, html, re.DOTALL))
        snippet_matches = list(re.finditer(snippet_pattern, html, re.DOTALL))

        for i, match in enumerate(title_url_matches):
            raw_url = match.group(1)
            title = self._strip_tags(match.group(2))

            # Decode DuckDuckGo redirect: extract uddg= param
            from urllib.parse import unquote, parse_qs, urlparse
            parsed = urlparse(raw_url)
            uddg = parse_qs(parsed.query).get("uddg")
            url = unquote(uddg[0]) if uddg else raw_url

            snippet = ""
            if i < len(snippet_matches):
                snippet = self._strip_tags(snippet_matches[i].group(1))

            if title:
                results.append({"title": title, "url": url, "snippet": snippet})

        return results
