"""Application layer - Use cases and MCP server setup."""

import json
from typing import Any

from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    INVALID_PARAMS,
    CallToolRequestParams,
    CallToolResult,
    ListResourcesResult,
    ListToolsResult,
    PaginatedRequestParams,
    ReadResourceRequestParams,
    ReadResourceResult,
    Resource,
    TextContent,
    TextResourceContents,
    Tool,
)

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

SEARCH_RESOURCE_URI = "searxng://web/search"


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
        return await self._search_port.search(query, parameters)

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


WEB_SEARCH_TOOL = Tool(
    name="web_search",
    title="SearXNG Web Search",
    description="Use SearXNG to search the web for information",
    input_schema={
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
                "description": f"Search language code (default {DEFAULT_LANGUAGE!r})",
            },
            "max_results": {
                "type": "integer",
                "description": (
                    f"Maximum number of results to return "
                    f"(default {DEFAULT_MAX_RESULTS})"
                ),
            },
            "time_range": {
                "type": "string",
                "description": "Time range filter ('day', 'week', 'month', 'year')",
            },
        },
        "required": ["query"],
    },
)

SEARCH_RESOURCE = Resource(
    uri=SEARCH_RESOURCE_URI,
    name="SearXNG Web Search",
    title="🔍 SearXNG Web Search",
    description=(
        "Search the web using SearXNG meta-search engine with support for "
        "multiple engines, categories, and filters"
    ),
    mime_type="application/json",
)

RESOURCE_INFO: dict[str, Any] = {
    "resource": "Web Search",
    "description": "Use SearXNG to search the web for information",
    "usage": {
        "tool_name": WEB_SEARCH_TOOL.name,
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


def _to_tool_result(results: SearchResultCollection) -> CallToolResult:
    """Render a result collection as an MCP tool result."""
    formatted = results.format_as_text()
    return CallToolResult(
        content=[TextContent(type="text", text=text) for text in formatted]
    )


def build_server(search_use_case: SearchUseCase) -> Server:
    """Wire the MCP server handlers to the given use case."""

    async def handle_list_resources(
        ctx: ServerRequestContext, params: PaginatedRequestParams | None
    ) -> ListResourcesResult:
        """List available search resources."""
        return ListResourcesResult(resources=[SEARCH_RESOURCE])

    async def handle_read_resource(
        ctx: ServerRequestContext, params: ReadResourceRequestParams
    ) -> ReadResourceResult:
        """Read specified search resource."""
        uri = str(params.uri)
        if uri != SEARCH_RESOURCE_URI:
            raise MCPError(INVALID_PARAMS, f"Unknown resource: {uri}")

        return ReadResourceResult(
            contents=[
                TextResourceContents(
                    uri=params.uri,
                    mime_type="application/json",
                    text=json.dumps(RESOURCE_INFO, ensure_ascii=False, indent=2),
                )
            ]
        )

    async def handle_list_tools(
        ctx: ServerRequestContext, params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        """List available search tools."""
        return ListToolsResult(tools=[WEB_SEARCH_TOOL])

    async def execute_web_search(arguments: dict[str, Any]) -> CallToolResult:
        """Execute web search with provided arguments."""
        query_text = arguments.get("query")
        if not query_text:
            raise ValueError("Missing required parameter: query")

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

        return _to_tool_result(results)

    async def handle_call_tool(
        ctx: ServerRequestContext, params: CallToolRequestParams
    ) -> CallToolResult:
        """Process tool call request."""
        if params.name != WEB_SEARCH_TOOL.name:
            raise MCPError(INVALID_PARAMS, f"Unsupported tool: {params.name}")

        return await execute_web_search(params.arguments or {})

    return Server(
        "SearXNGServer",
        on_list_resources=handle_list_resources,
        on_read_resource=handle_read_resource,
        on_list_tools=handle_list_tools,
        on_call_tool=handle_call_tool,
    )


async def serve(instance_url: str = "https://searx.party") -> None:
    """Start SearXNG MCP server."""
    from searxng.adapters import HttpSearchAdapter

    search_adapter = HttpSearchAdapter(instance_url=instance_url)
    server = build_server(SearchUseCase(search_port=search_adapter))

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
