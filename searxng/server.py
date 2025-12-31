"""Application layer - Use cases and MCP server setup."""

import json
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import McpError
from mcp.types import (
    EmbeddedResource,
    ErrorData,
    ImageContent,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from searxng.client import (
    SearchParameters,
    SearchPort,
    SearchQuery,
    SearchResultCollection,
)

DEFAULT_CATEGORIES = ("general",)
DEFAULT_ENGINES = ("google", "bing", "duckduckgo")
DEFAULT_LANGUAGE = "en"
DEFAULT_MAX_RESULTS = 10


class SearchUseCase:
    """Use case for performing web searches."""

    def __init__(self, search_port: SearchPort) -> None:
        self._search_port = search_port

    async def execute(
        self,
        query_text: str,
        categories: tuple[str, ...] | None,
        engines: tuple[str, ...] | None,
        language: str,
        max_results: int,
        time_range: str | None,
    ) -> SearchResultCollection:
        """Execute search operation."""
        query = SearchQuery(text=query_text)
        parameters = self._create_parameters(
            categories, engines, language, max_results, time_range
        )
        return self._search_port.search(query, parameters)

    def _create_parameters(
        self,
        categories: tuple[str, ...] | None,
        engines: tuple[str, ...] | None,
        language: str,
        max_results: int,
        time_range: str | None,
    ) -> SearchParameters:
        """Create search parameters with defaults."""
        return SearchParameters(
            categories=categories or DEFAULT_CATEGORIES,
            engines=engines or DEFAULT_ENGINES,
            language=language,
            max_results=max_results,
            time_range=time_range,
        )


async def serve(instance_url: str = "https://searx.party") -> None:
    """Start SearXNG MCP server."""
    from searxng.adapters import HttpSearchAdapter

    server = Server("SearXNGServer")
    search_adapter = HttpSearchAdapter(instance_url=instance_url)
    search_use_case = SearchUseCase(search_port=search_adapter)

    @server.list_resources()
    async def handle_list_resources() -> list:
        """List available search resources."""
        return [
            {
                "uri": "searxng://web/search",
                "name": "SearXNG Web Search",
                "title": "🔍 SearXNG Web Search",
                "description": "Search the web using SearXNG meta-search engine with support for multiple engines, categories, and filters",
                "mimeType": "application/json",
            }
        ]

    @server.read_resource()
    async def handle_read_resource(
        uri: AnyUrl,
    ) -> str:
        """Read specified search resource."""
        uri_str = str(uri)
        if not uri_str.startswith("searxng://"):
            raise ValueError(f"Unsupported URI: {uri_str}")

        if uri_str != "searxng://web/search":
            raise ValueError(f"Unknown resource: {uri_str}")

        resource_info = {
            "resource": "Web Search",
            "description": "Use SearXNG to search the web for information",
            "usage": {
                "tool_name": "web_search",
                "required_parameters": ["query"],
                "optional_parameters": {
                    "categories": {
                        "type": "array",
                        "description": "Search categories",
                        "default": list(DEFAULT_CATEGORIES),
                        "examples": ["general", "images", "news", "videos"],
                    },
                    "engines": {
                        "type": "array",
                        "description": "Search engines to use",
                        "default": list(DEFAULT_ENGINES),
                        "examples": ["google", "bing", "duckduckgo", "brave"],
                    },
                    "language": {
                        "type": "string",
                        "description": "Search language code",
                        "default": DEFAULT_LANGUAGE,
                        "examples": ["en", "es", "fr", "de"],
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": DEFAULT_MAX_RESULTS,
                        "range": "1-100",
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Filter results by time",
                        "options": ["day", "week", "month", "year"],
                    },
                },
            },
            "examples": [
                {
                    "description": "Basic search",
                    "query": "python programming",
                },
                {
                    "description": "Search with specific engines",
                    "query": "artificial intelligence",
                    "engines": ["google", "bing"],
                },
                {
                    "description": "Recent news search",
                    "query": "technology news",
                    "categories": ["news"],
                    "time_range": "week",
                },
            ],
        }

        return json.dumps(resource_info, ensure_ascii=False, indent=2)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available search tools."""
        return [
            Tool(
                name="web_search",
                description="Use SearXNG to search the web for information",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Search categories, e.g. ['general', 'images', 'news']",
                        },
                        "engines": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Search engines, e.g. ['google', 'bing', 'duckduckgo']",
                        },
                        "language": {
                            "type": "string",
                            "description": "Search language code (default 'en')",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 10)",
                        },
                        "time_range": {
                            "type": "string",
                            "description": "Time range filter ('day', 'week', 'month', 'year')",
                        },
                    },
                    "required": ["query"],
                },
            )
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Process tool call request."""
        if name != "web_search":
            return [
                TextContent(
                    type="text",
                    text=f"Unsupported tool: {name}",
                )
            ]

        return await execute_web_search(arguments)

    async def execute_web_search(
        arguments: dict[str, Any],
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Execute web search with provided arguments."""
        query_text = arguments.get("query")
        if not query_text:
            raise ValueError("Missing required parameter: query")

        try:
            categories_list = arguments.get("categories")
            engines_list = arguments.get("engines")

            results = await search_use_case.execute(
                query_text=query_text,
                categories=tuple(categories_list) if categories_list else None,
                engines=tuple(engines_list) if engines_list else None,
                language=arguments.get("language", DEFAULT_LANGUAGE),
                max_results=arguments.get("max_results", DEFAULT_MAX_RESULTS),
                time_range=arguments.get("time_range"),
            )

            formatted_results = results.format_as_text()
            return [
                TextContent(type="text", text=result) for result in formatted_results
            ]

        except Exception as e:
            error = ErrorData(
                message=f"Search service error: {e}",
                code=-32603,
            )
            raise McpError(error) from e

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
