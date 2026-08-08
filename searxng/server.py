"""Application layer - Use cases and MCP server setup."""

import json
import logging
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
    MAX_RESULTS_LIMIT,
    VALID_TIME_RANGES,
    SearchError,
    SearchParameters,
    SearchPort,
    SearchQuery,
    SearchResultCollection,
)

DEFAULT_CATEGORIES = ("general",)
DEFAULT_ENGINES = ("google", "bing", "duckduckgo")
DEFAULT_LANGUAGE = "en"
DEFAULT_MAX_RESULTS = 10
DEFAULT_INSTANCE_URL = "https://searx.party"

# "sse" is intentionally absent: it was superseded by Streamable HTTP in the
# 2025-03-26 protocol revision and should not be used for new deployments.
VALID_TRANSPORTS = frozenset({"stdio", "http"})
DEFAULT_TRANSPORT = "stdio"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
STREAMABLE_HTTP_PATH = "/mcp"
# Hosts for which the MCP SDK auto-enables DNS-rebinding protection.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

SEARCH_RESOURCE_URI = "searxng://web/search"

logger = logging.getLogger(__name__)


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
                "minLength": 1,
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
                "minimum": 1,
                "maximum": MAX_RESULTS_LIMIT,
            },
            "time_range": {
                "type": "string",
                "description": "Time range filter",
                "enum": sorted(VALID_TIME_RANGES),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
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
                "range": f"1-{MAX_RESULTS_LIMIT}",
            },
            "time_range": {
                "type": "string",
                "description": "Filter results by time",
                "options": sorted(VALID_TIME_RANGES),
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


def _coerce_str_tuple(value: Any, field: str) -> tuple[str, ...] | None:
    """Validate an optional list-of-strings argument."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"'{field}' must be an array of strings")
    return tuple(value) or None


def _coerce_language(value: Any) -> str:
    """Validate the optional language argument."""
    if value is None:
        return DEFAULT_LANGUAGE
    if not isinstance(value, str) or not value.strip():
        raise ValueError("'language' must be a non-empty string")
    return value


def _coerce_max_results(value: Any) -> int:
    """Validate the optional max_results argument."""
    if value is None:
        return DEFAULT_MAX_RESULTS
    # bool is a subclass of int, but is never a valid result count.
    if isinstance(value, bool) or not isinstance(value, int):
        # ValueError keeps argument validation on one error path with the
        # domain's own checks, which the tool handler reports back to the model.
        raise ValueError("'max_results' must be an integer")  # noqa: TRY004
    return value


def _to_tool_result(results: SearchResultCollection) -> CallToolResult:
    """Render a result collection as an MCP tool result."""
    formatted = results.format_as_text()
    if not formatted:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"No results found for {results.query.text!r}.",
                )
            ]
        )

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
        try:
            query_text = arguments.get("query")
            if not isinstance(query_text, str) or not query_text.strip():
                raise ValueError("Missing required parameter: query")

            results = await search_use_case.execute(
                query_text=query_text,
                categories=_coerce_str_tuple(arguments.get("categories"), "categories"),
                engines=_coerce_str_tuple(arguments.get("engines"), "engines"),
                language=_coerce_language(arguments.get("language")),
                max_results=_coerce_max_results(arguments.get("max_results")),
                time_range=arguments.get("time_range"),
            )
        except (ValueError, SearchError) as e:
            # Tool-level failure: report it to the model so it can self-correct.
            logger.warning("web_search failed: %s", e)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Search failed: {e}")],
                is_error=True,
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


async def _serve_stdio(server: Server) -> None:
    """Serve over stdio, the transport local MCP clients launch us with."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def _serve_http(server: Server, host: str, port: int) -> None:
    """Serve over Streamable HTTP for remote clients.

    Streamable HTTP superseded the SSE transport in the 2025-03-26 protocol
    revision; new deployments should use this rather than ``/sse``.
    """
    import uvicorn

    if host not in LOOPBACK_HOSTS:
        # The SDK only auto-enables DNS-rebinding protection for loopback
        # binds, since it cannot infer valid hostnames for a public one.
        # Say so plainly rather than letting the protection lapse silently.
        logger.warning(
            "Serving on %s:%s without authentication or DNS-rebinding "
            "protection. Restrict this to a trusted network or place an "
            "authenticating reverse proxy in front of it.",
            host,
            port,
        )

    app = server.streamable_http_app(
        streamable_http_path=STREAMABLE_HTTP_PATH,
        host=host,
    )
    config = uvicorn.Config(app, host=host, port=port, log_config=None)
    await uvicorn.Server(config).serve()


async def serve(
    instance_url: str = DEFAULT_INSTANCE_URL,
    timeout: int = 30,
    transport: str = DEFAULT_TRANSPORT,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    """Start SearXNG MCP server on the requested transport."""
    from searxng.adapters import HttpSearchAdapter

    if transport not in VALID_TRANSPORTS:
        valid = ", ".join(sorted(VALID_TRANSPORTS))
        raise ValueError(f"Transport must be one of: {valid}")

    search_adapter = HttpSearchAdapter(instance_url=instance_url, timeout=timeout)
    server = build_server(SearchUseCase(search_port=search_adapter))

    try:
        if transport == "http":
            await _serve_http(server, host=host, port=port)
        else:
            await _serve_stdio(server)
    finally:
        search_adapter.close()
