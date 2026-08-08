"""Tests for application layer (server module)."""

import json
from typing import Any
from unittest.mock import Mock, patch

import pytest
from mcp import MCPError
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceRequestParams,
    ReadResourceResult,
    TextContent,
    TextResourceContents,
)

from searxng.client import (
    ResultIndex,
    SearchError,
    SearchParameters,
    SearchQuery,
    SearchResult,
    SearchResultCollection,
    SearchResultContent,
    SearchResultTitle,
    SearchResultUrl,
)
from searxng.server import (
    DEFAULT_CATEGORIES,
    DEFAULT_ENGINES,
    SEARCH_RESOURCE_URI,
    SearchUseCase,
    build_server,
)


def make_collection(*titles: str, query: str = "test") -> SearchResultCollection:
    """Build a result collection with one entry per title."""
    return SearchResultCollection(
        query=SearchQuery(text=query),
        results=tuple(
            SearchResult(
                index=ResultIndex(value=i),
                title=SearchResultTitle(value=title),
                url=SearchResultUrl(value=f"https://example.com/{i}"),
                content=SearchResultContent(value=f"content {i}"),
            )
            for i, title in enumerate(titles)
        ),
    )


def make_use_case(
    return_value: SearchResultCollection | None = None,
    side_effect: Exception | None = None,
) -> tuple[SearchUseCase, Mock]:
    """Build a SearchUseCase backed by a mock port."""
    port = Mock()
    if side_effect is not None:

        async def raise_side_effect(*args: Any, **kwargs: Any) -> None:
            raise side_effect

        port.search = raise_side_effect
    else:
        collection = return_value if return_value is not None else make_collection()

        async def return_collection(
            *args: Any, **kwargs: Any
        ) -> SearchResultCollection:
            return collection

        port.search = return_collection
    return SearchUseCase(search_port=port), port


def handler_for(server: Any, method: str) -> Any:
    """Look up a registered request handler by its MCP method name."""
    return server._request_handlers[method].handler


async def call_tool(
    server: Any, name: str, arguments: dict[str, Any]
) -> CallToolResult:
    """Invoke the tools/call handler directly."""
    handler = handler_for(server, "tools/call")
    return await handler(Mock(), CallToolRequestParams(name=name, arguments=arguments))


def text_at(result: CallToolResult, index: int) -> str:
    """Return the text of a content block, asserting it is a text block."""
    block = result.content[index]
    assert isinstance(block, TextContent)
    return block.text


class TestSearchUseCase:
    """Test SearchUseCase application service."""

    async def test_execute_with_all_parameters(self) -> None:
        """Test executing search with all parameters."""
        use_case, port = make_use_case()

        with patch.object(port, "search", wraps=port.search) as spy:
            await use_case.execute(
                query_text="test query",
                categories=("general", "news"),
                engines=("google", "bing"),
                language="en",
                max_results=15,
                time_range="week",
            )

        spy.assert_called_once()
        query, parameters = spy.call_args.args
        assert query.text == "test query"
        assert parameters.categories == ("general", "news")
        assert parameters.engines == ("google", "bing")
        assert parameters.language == "en"
        assert parameters.max_results == 15
        assert parameters.time_range == "week"

    async def test_execute_with_defaults(self) -> None:
        """Test executing search with default parameters."""
        use_case, port = make_use_case()

        with patch.object(port, "search", wraps=port.search) as spy:
            await use_case.execute(
                query_text="test",
                categories=None,
                engines=None,
                language="en",
                max_results=10,
                time_range=None,
            )

        _, parameters = spy.call_args.args
        assert parameters.categories == DEFAULT_CATEGORIES
        assert parameters.engines == DEFAULT_ENGINES
        assert parameters.time_range is None

    async def test_execute_creates_valid_search_query(self) -> None:
        """Test that execute creates valid SearchQuery."""
        use_case, port = make_use_case()

        with patch.object(port, "search", wraps=port.search) as spy:
            await use_case.execute(
                query_text="Python programming",
                categories=None,
                engines=None,
                language="en",
                max_results=10,
                time_range=None,
            )

        query, _ = spy.call_args.args
        assert isinstance(query, SearchQuery)
        assert query.text == "Python programming"

    async def test_execute_creates_valid_search_parameters(self) -> None:
        """Test that execute creates valid SearchParameters."""
        use_case, port = make_use_case()

        with patch.object(port, "search", wraps=port.search) as spy:
            await use_case.execute(
                query_text="test",
                categories=("images",),
                engines=("duckduckgo",),
                language="fr",
                max_results=20,
                time_range="day",
            )

        _, parameters = spy.call_args.args
        assert isinstance(parameters, SearchParameters)
        assert parameters.categories == ("images",)
        assert parameters.engines == ("duckduckgo",)
        assert parameters.language == "fr"
        assert parameters.max_results == 20
        assert parameters.time_range == "day"

    async def test_execute_with_empty_tuples_uses_defaults(self) -> None:
        """Test that empty tuples fall back to defaults."""
        use_case, port = make_use_case()

        with patch.object(port, "search", wraps=port.search) as spy:
            await use_case.execute(
                query_text="test",
                categories=(),
                engines=(),
                language="en",
                max_results=10,
                time_range=None,
            )

        _, parameters = spy.call_args.args
        assert parameters.categories == DEFAULT_CATEGORIES
        assert parameters.engines == DEFAULT_ENGINES


class TestListHandlers:
    """Test the resource and tool listing handlers."""

    async def test_list_resources(self) -> None:
        """Test the resources/list handler."""
        server = build_server(make_use_case()[0])

        result = await handler_for(server, "resources/list")(Mock(), None)

        assert isinstance(result, ListResourcesResult)
        assert [str(r.uri) for r in result.resources] == [SEARCH_RESOURCE_URI]

    async def test_list_tools(self) -> None:
        """Test the tools/list handler."""
        server = build_server(make_use_case()[0])

        result = await handler_for(server, "tools/list")(Mock(), None)

        assert isinstance(result, ListToolsResult)
        assert len(result.tools) == 1
        assert result.tools[0].name == "web_search"
        assert result.tools[0].description is not None
        assert "SearXNG" in result.tools[0].description


class TestReadResourceHandler:
    """Test the resources/read handler."""

    async def test_reads_the_search_resource(self) -> None:
        """Test the read_resource handler with a valid URI."""
        server = build_server(make_use_case()[0])

        result = await handler_for(server, "resources/read")(
            Mock(), ReadResourceRequestParams(uri=SEARCH_RESOURCE_URI)
        )

        assert isinstance(result, ReadResourceResult)
        contents = result.contents[0]
        assert isinstance(contents, TextResourceContents)
        payload = json.loads(contents.text)
        assert payload["resource"] == "Web Search"
        assert payload["usage"]["tool_name"] == "web_search"
        assert "query" in payload["usage"]["required_parameters"]
        assert len(payload["examples"]) == 3

    async def test_rejects_unknown_uri(self) -> None:
        """Test the read_resource handler with an unknown searxng resource."""
        server = build_server(make_use_case()[0])

        with pytest.raises(MCPError, match="Unknown resource"):
            await handler_for(server, "resources/read")(
                Mock(), ReadResourceRequestParams(uri="searxng://unknown")
            )


class TestCallToolHandler:
    """Test the tools/call handler."""

    async def test_unsupported_tool_raises_protocol_error(self) -> None:
        """Test call_tool with an unsupported tool name."""
        server = build_server(make_use_case()[0])

        with pytest.raises(MCPError, match="Unsupported tool"):
            await call_tool(server, "unsupported_tool", {})

    async def test_successful_search_returns_formatted_results(self) -> None:
        """Test successful web search execution."""
        use_case, _ = make_use_case(return_value=make_collection("Test"))
        server = build_server(use_case)

        result = await call_tool(server, "web_search", {"query": "test"})

        assert len(result.content) == 1
        assert "Test" in text_at(result, 0)

    async def test_search_exception_propagates(self) -> None:
        """Test that an unexpected search failure propagates to the caller."""
        use_case, _ = make_use_case(side_effect=RuntimeError("Test error"))
        server = build_server(use_case)

        with pytest.raises(RuntimeError, match="Test error"):
            await call_tool(server, "web_search", {"query": "test"})

    async def test_search_error_returns_tool_error(self) -> None:
        """A SearchError from the port is reported to the model, not raised."""
        use_case, _ = make_use_case(side_effect=SearchError("instance unreachable"))
        server = build_server(use_case)

        result = await call_tool(server, "web_search", {"query": "test"})

        assert result.is_error is True
        assert "instance unreachable" in text_at(result, 0)

    async def test_missing_query_returns_tool_error(self) -> None:
        """A missing query is a tool-level error, not a protocol error."""
        server = build_server(make_use_case()[0])

        result = await call_tool(server, "web_search", {})

        assert result.is_error is True
        assert "Missing required parameter" in text_at(result, 0)


class TestServeFunction:
    """Test the serve function and MCP server setup."""

    async def test_serve_wires_adapter_and_runs_server(self) -> None:
        """Test that serve initializes the adapter and runs the server."""
        from unittest.mock import AsyncMock

        from searxng.server import serve

        mock_adapter = Mock()

        with (
            patch(
                "searxng.adapters.HttpSearchAdapter", return_value=mock_adapter
            ) as mock_adapter_cls,
            patch("searxng.server.stdio_server") as mock_stdio,
            patch("searxng.server.build_server") as mock_build,
        ):
            mock_stdio.return_value.__aenter__ = AsyncMock(
                return_value=(Mock(), Mock())
            )
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_build.return_value.run = AsyncMock()

            await serve(instance_url="https://test.searx")

        mock_adapter_cls.assert_called_once_with(instance_url="https://test.searx")
        mock_build.return_value.run.assert_awaited_once()
        mock_adapter.close.assert_called_once()

    async def test_serve_closes_adapter_on_failure(self) -> None:
        """The adapter's connection pool is released even if the server loop raises."""
        from unittest.mock import AsyncMock

        from searxng.server import serve

        mock_adapter = Mock()

        with (
            patch("searxng.adapters.HttpSearchAdapter", return_value=mock_adapter),
            patch("searxng.server.stdio_server") as mock_stdio,
            patch("searxng.server.build_server") as mock_build,
        ):
            mock_stdio.return_value.__aenter__ = AsyncMock(
                return_value=(Mock(), Mock())
            )
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_build.return_value.run = AsyncMock(side_effect=RuntimeError("boom"))

            with pytest.raises(RuntimeError, match="boom"):
                await serve()

        mock_adapter.close.assert_called_once()
