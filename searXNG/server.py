import json
from typing import Any, Sequence, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource, ErrorData, TextResourceContents, \
    BlobResourceContents
from mcp.shared.exceptions import McpError

from .client import SearXNGClient


class SearXNGServer:
    """
    SearXNG MCP Server
    Provides search functionality for models to use through the MCP interface
    """

    def __init__(self, instance_url: str = "https://searx.party"):
        """
        Initialize SearXNG server

        Parameters:
        - instance_url: SearXNG instance URL
        """
        self.searxng_client = SearXNGClient(instance_url=instance_url)

    async def search(self, query: str, categories: Optional[List[str]] = None,
                     engines: Optional[List[str]] = None,
                     language: str = "en",
                     max_results: int = 10,
                     time_range: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform search and return formatted results

        Parameters:
        - query: search query
        - categories: search category list (e.g. ['general', 'images', 'news'])
        - engines: search engine list (e.g. ['google', 'bing', 'duckduckgo'])
        - language: search language code
        - max_results: maximum result count
        - time_range: time range filter ('day', 'week', 'month', 'year')

        Returns:
        - Structured search results dictionary
        """
        # Set default search parameters
        if categories is None:
            categories = ["general"]
        if engines is None:
            engines = ["google", "bing", "duckduckgo"]

        # Use SearXNG client to perform search
        search_results = self.searxng_client.search(
            query=query,
            categories=categories,
            engines=engines,
            language=language,
            max_results=max_results,
            time_range=time_range,
            safesearch=1
        )

        return search_results

    def format_search_results(self, search_results: Dict[str, Any]) -> str:
        """
        Format search results into text output

        Parameters:
        - search_results: search results dictionary

        Returns:
        - Formatted search results text
        """
        # Build formatted output
        output = []
        # Add content results
        content_items = search_results.get('content', [])
        if content_items:
            for item in content_items:
                output.append(f"[{item.get('index', '')}] {item.get('result', '')}")
            output.append("")

        return "\n".join(output)


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
    async def handle_read_resource(uri: str) -> List[TextResourceContents | BlobResourceContents]:
        """Read specified search resource"""
        if uri.startswith("searxng://"):
            # Create a text resource content object with a placeholder message
            return [
                TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=json.dumps({"message": "This feature is not yet implemented"}, ensure_ascii=False)
                )
            ]
        raise ValueError(f"Unsupported URI: {uri}")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
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
                        }
                    },
                    "required": ["query"],
                }
            )
        ]

    @server.call_tool()
    async def call_tool(
            name: str, arguments: Dict[str, Any]
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Processing tool call request"""
        try:
            if name == "web_search":
                query = arguments.get("query")
                if not query:
                    raise ValueError("Missing required parameter: query")

                categories = arguments.get("categories")
                engines = arguments.get("engines")
                language = arguments.get("language", "en")
                max_results = arguments.get("max_results", 10)
                time_range = arguments.get("time_range")

                search_results = await searxng_server.search(
                    query=query,
                    categories=categories,
                    engines=engines,
                    language=language,
                    max_results=max_results,
                    time_range=time_range
                )

                formatted_results = searxng_server.format_search_results(search_results)

                return [TextContent(type="text", text=formatted_results)]

            return [TextContent(type="text", text=f"Unsupported tool: {name}")]

        except Exception as e:
            error = ErrorData(message=f"Search service error: {str(e)}", code=-32603)
            raise McpError(error)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
