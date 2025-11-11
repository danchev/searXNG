import json
from typing import Any, Optional, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import McpError
from mcp.types import (
    BlobResourceContents,
    EmbeddedResource,
    ErrorData,
    Icon,
    ImageContent,
    TextContent,
    TextResourceContents,
    Tool,
    ToolAnnotations,
)
from pydantic import AnyUrl

from searxng.client import SearXNGClient

# Default SearXNG search parameters
DEFAULT_CATEGORIES = ["general"]
DEFAULT_ENGINES = ["google", "bing", "duckduckgo"]
DEFAULT_LANGUAGE = "en"
DEFAULT_MAX_RESULTS = 10
DEFAULT_SAFESEARCH = 1


class SearXNGServer:
    """
    SearXNG MCP Server
    Provides search functionality for models to use through the MCP interface.

    Search results include for each result: index, title, url, and result (content).
    """

    def __init__(self, instance_url: str = "https://searx.party"):
        """
        Initialize SearXNG server

        Parameters:
        - instance_url: SearXNG instance URL
        """
        self.searxng_client = SearXNGClient(instance_url=instance_url)

    async def search(
        self,
        query: str,
        categories: Optional[list[str]] = None,
        engines: Optional[list[str]] = None,
        language: str = DEFAULT_LANGUAGE,
        max_results: int = DEFAULT_MAX_RESULTS,
        time_range: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Perform search and return formatted results.

        Args:
            query: Search query string.
            categories: List of search categories (e.g. ['general', 'images', 'news']).
            engines: List of search engines (e.g. ['google', 'bing', 'duckduckgo']).
            language: Search language code.
            max_results: Maximum number of results to return.
            time_range: Time range filter ('day', 'week', 'month', 'year').

        Returns:
            dict: Structured search results dictionary with keys:
                - query: The original query string.
                - content: List of results, each containing:
                    - index: Result index.
                    - title: Result title.
                    - url: Result URL.
                    - result: Result content/summary.
        """
        # Set default search parameters
        if categories is None:
            categories = DEFAULT_CATEGORIES.copy()
        if engines is None:
            engines = DEFAULT_ENGINES.copy()

        # Use SearXNG client to perform search
        search_results = self.searxng_client.search(
            query=query,
            categories=categories,
            engines=engines,
            language=language,
            max_results=max_results,
            time_range=time_range,
            safesearch=DEFAULT_SAFESEARCH,
        )

        return search_results

    def format_search_results(self, search_results: dict[str, Any]) -> list[str]:
        """
        Format search results into text output.

        Args:
            search_results: Search results dictionary as returned by `search()`.

        Returns:
            str: Formatted search results text, each line includes index, title, url, and result content.
        """
        # Build formatted output
        output = []
        # Add content results
        content_items = search_results.get("content", [])
        if content_items:
            for item in content_items:
                index = item.get("index", "")
                title = item.get("title", "")
                url = item.get("url", "")
                result = item.get("result", "")
                output.append(f"[{index}] {title}\nURL: {url}\n{result}\n")

        return output


async def serve(instance_url: str = "https://searx.party"):
    """
    Start SearXNG MCP server

    Parameters:
    - instance_url: SearXNG instance URL
    """
    server = Server("SearXNGServer")
    searxng_server = SearXNGServer(instance_url=instance_url)

    @server.list_resources()
    async def handle_list_resources():
        """List available search resources"""
        return [
            {
                "uri": "searxng://web/search",
                "name": "Web Search",
                "description": "Use SearXNG to search the web for information",
                "mimeType": "application/json",
            }
        ]

    @server.read_resource()
    async def handle_read_resource(
        uri: str,
    ) -> list[TextResourceContents | BlobResourceContents]:
        """Read specified search resource"""
        if uri.startswith("searxng://"):
            # Create a text resource content object with a placeholder message
            return [
                TextResourceContents(
                    uri=AnyUrl(uri),
                    mimeType="application/json",
                    text=json.dumps(
                        {"message": "This feature is not yet implemented"},
                        ensure_ascii=False,
                    ),
                )
            ]
        raise ValueError(f"Unsupported URI: {uri}")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available search tools"""
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
                title="Web Search Tool",
                outputSchema=None,
                icons=[
                    Icon(
                        src="search-icon.png",
                        mimeType="image/png",
                        sizes=["32x32"],
                        model_config={},
                    ),
                ],
                annotations=ToolAnnotations(
                    title="SearXNG Tool",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                    model_config={"version": "1.0"},
                ),
                meta={
                    "category": "search",
                    "tags": ["web", "search", "tool"],
                },
                model_config={
                    "timeout": 30,
                    "retry": 3,
                },
            )
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Processing tool call request"""
        try:
            if name == "web_search":
                query = arguments.get("query")
                if not query:
                    raise ValueError("Missing required parameter: query")

                categories = arguments.get("categories")
                engines = arguments.get("engines")
                language = arguments.get("language", DEFAULT_LANGUAGE)
                max_results = arguments.get("max_results", DEFAULT_MAX_RESULTS)
                time_range = arguments.get("time_range")

                search_results = await searxng_server.search(
                    query=query,
                    categories=categories,
                    engines=engines,
                    language=language,
                    max_results=max_results,
                    time_range=time_range,
                )

                formatted_results = searxng_server.format_search_results(search_results)

                return [
                    TextContent(
                        type="text",
                        text=result,
                    ) for result in formatted_results
                ]

            return [
                TextContent(
                    type="text",
                    text=f"Unsupported tool: {name}",
                )
            ]

        except Exception as e:
            error = ErrorData(
                message=f"Search service error: {e}",
                code=-32603,
            )
            raise McpError(error)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
