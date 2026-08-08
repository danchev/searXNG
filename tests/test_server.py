"""Tests for application layer (server module)."""

import json
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

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
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_RESULTS,
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
        # Setting return_value alongside side_effect leaves an un-awaited
        # coroutine behind, so configure exactly one of the two.
        port.search = AsyncMock(side_effect=side_effect)
    else:
        port.search = AsyncMock(
            return_value=return_value if return_value is not None else make_collection()
        )
    return SearchUseCase(search_port=port), port


def make_ctx() -> Any:
    """A request-context stand-in; handlers here do not use it."""
    return SimpleNamespace()


def handler_for(server: Any, method: str) -> Any:
    """Look up a registered request handler by its MCP method name."""
    return server._request_handlers[method].handler


async def call_tool(
    server: Any, name: str, arguments: dict[str, Any]
) -> CallToolResult:
    """Invoke the tools/call handler directly."""
    handler = handler_for(server, "tools/call")
    return await handler(
        make_ctx(), CallToolRequestParams(name=name, arguments=arguments)
    )


def text_at(result: CallToolResult, index: int) -> str:
    """Return the text of a content block, asserting it is a text block."""
    block = result.content[index]
    assert isinstance(block, TextContent)
    return block.text


class TestSearchUseCase:
    """Test the search use case."""

    async def test_execute_with_all_parameters(self) -> None:
        """All explicit parameters are forwarded to the port."""
        use_case, port = make_use_case()

        await use_case.execute(
            query_text="test query",
            categories=("news",),
            engines=("bing",),
            language="fr",
            max_results=5,
            time_range="week",
        )

        query, parameters = port.search.call_args.args
        assert query.text == "test query"
        assert parameters.categories == ("news",)
        assert parameters.engines == ("bing",)
        assert parameters.language == "fr"
        assert parameters.max_results == 5
        assert parameters.time_range == "week"

    async def test_execute_with_defaults(self) -> None:
        """Omitted categories and engines fall back to defaults."""
        use_case, port = make_use_case()

        await use_case.execute(
            query_text="test",
            categories=None,
            engines=None,
            language=DEFAULT_LANGUAGE,
            max_results=DEFAULT_MAX_RESULTS,
            time_range=None,
        )

        _, parameters = port.search.call_args.args
        assert parameters.categories == DEFAULT_CATEGORIES
        assert parameters.engines == DEFAULT_ENGINES

    async def test_execute_with_empty_tuples_uses_defaults(self) -> None:
        """Empty tuples are treated as 'unspecified'."""
        use_case, port = make_use_case()

        await use_case.execute(
            query_text="test",
            categories=(),
            engines=(),
            language=DEFAULT_LANGUAGE,
            max_results=DEFAULT_MAX_RESULTS,
            time_range=None,
        )

        _, parameters = port.search.call_args.args
        assert parameters.categories == DEFAULT_CATEGORIES
        assert parameters.engines == DEFAULT_ENGINES

    async def test_execute_creates_valid_search_query(self) -> None:
        """The raw query text becomes a SearchQuery value object."""
        use_case, port = make_use_case()

        await use_case.execute(
            query_text="python programming",
            categories=None,
            engines=None,
            language=DEFAULT_LANGUAGE,
            max_results=DEFAULT_MAX_RESULTS,
            time_range=None,
        )

        query, _ = port.search.call_args.args
        assert isinstance(query, SearchQuery)
        assert query.text == "python programming"

    async def test_execute_rejects_empty_query(self) -> None:
        """An empty query is rejected before reaching the port."""
        use_case, port = make_use_case()

        with pytest.raises(ValueError, match="cannot be empty"):
            await use_case.execute(
                query_text="   ",
                categories=None,
                engines=None,
                language=DEFAULT_LANGUAGE,
                max_results=DEFAULT_MAX_RESULTS,
                time_range=None,
            )

        port.search.assert_not_called()

    async def test_execute_returns_port_results(self) -> None:
        """The collection from the port is returned unchanged."""
        expected = make_collection("A", "B")
        use_case, _ = make_use_case(return_value=expected)

        result = await use_case.execute(
            query_text="test",
            categories=None,
            engines=None,
            language=DEFAULT_LANGUAGE,
            max_results=DEFAULT_MAX_RESULTS,
            time_range=None,
        )

        assert result is expected


class TestListHandlers:
    """Test the resource and tool listing handlers."""

    async def test_list_resources(self) -> None:
        """The search resource is advertised."""
        server = build_server(make_use_case()[0])

        result = await handler_for(server, "resources/list")(make_ctx(), None)

        assert isinstance(result, ListResourcesResult)
        assert [str(r.uri) for r in result.resources] == [SEARCH_RESOURCE_URI]

    async def test_list_tools(self) -> None:
        """The web_search tool is advertised with a valid schema."""
        server = build_server(make_use_case()[0])

        result = await handler_for(server, "tools/list")(make_ctx(), None)

        assert isinstance(result, ListToolsResult)
        assert len(result.tools) == 1
        tool = result.tools[0]
        assert tool.name == "web_search"
        assert tool.input_schema["required"] == ["query"]
        assert "query" in tool.input_schema["properties"]

    async def test_tool_schema_constrains_max_results(self) -> None:
        """The advertised schema documents the max_results bounds."""
        server = build_server(make_use_case()[0])

        result = await handler_for(server, "tools/list")(make_ctx(), None)

        max_results = result.tools[0].input_schema["properties"]["max_results"]
        assert max_results["minimum"] == 1
        assert max_results["maximum"] == 100

    async def test_tool_schema_constrains_time_range(self) -> None:
        """The advertised schema enumerates valid time ranges."""
        server = build_server(make_use_case()[0])

        result = await handler_for(server, "tools/list")(make_ctx(), None)

        time_range = result.tools[0].input_schema["properties"]["time_range"]
        assert set(time_range["enum"]) == {"day", "week", "month", "year"}


class TestReadResourceHandler:
    """Test the resources/read handler."""

    async def test_reads_the_search_resource(self) -> None:
        """The known URI returns JSON usage documentation."""
        server = build_server(make_use_case()[0])

        result = await handler_for(server, "resources/read")(
            make_ctx(), ReadResourceRequestParams(uri=SEARCH_RESOURCE_URI)
        )

        assert isinstance(result, ReadResourceResult)
        contents = result.contents[0]
        assert isinstance(contents, TextResourceContents)
        assert contents.mime_type == "application/json"
        payload = json.loads(contents.text)
        assert payload["usage"]["tool_name"] == "web_search"
        assert payload["usage"]["required_parameters"] == ["query"]

    @pytest.mark.parametrize(
        "uri", ["searxng://web/unknown", "https://example.com", "searxng://other"]
    )
    async def test_rejects_unknown_uri(self, uri: str) -> None:
        """Any other URI is a protocol-level error."""
        server = build_server(make_use_case()[0])

        with pytest.raises(MCPError, match="Unknown resource"):
            await handler_for(server, "resources/read")(
                make_ctx(), ReadResourceRequestParams(uri=uri)
            )


class TestCallToolHandler:
    """Test the tools/call handler."""

    async def test_unsupported_tool_raises_protocol_error(self) -> None:
        """An unknown tool name is a protocol error, not a tool result."""
        server = build_server(make_use_case()[0])

        with pytest.raises(MCPError, match="Unsupported tool"):
            await call_tool(server, "nope", {"query": "test"})

    async def test_successful_search_returns_formatted_results(self) -> None:
        """Each result becomes a text content block."""
        use_case, _ = make_use_case(return_value=make_collection("First", "Second"))
        server = build_server(use_case)

        result = await call_tool(server, "web_search", {"query": "test"})

        assert result.is_error is not True
        assert len(result.content) == 2
        assert "First" in text_at(result, 0)
        assert "Second" in text_at(result, 1)

    async def test_empty_results_reported_as_text(self) -> None:
        """No results is a successful call, not an error."""
        use_case, _ = make_use_case(return_value=make_collection(query="obscure"))
        server = build_server(use_case)

        result = await call_tool(server, "web_search", {"query": "obscure"})

        assert result.is_error is not True
        assert "No results found" in text_at(result, 0)

    async def test_forwards_optional_arguments(self) -> None:
        """Optional tool arguments reach the use case."""
        use_case, port = make_use_case()
        server = build_server(use_case)

        await call_tool(
            server,
            "web_search",
            {
                "query": "test",
                "categories": ["news"],
                "engines": ["bing"],
                "language": "de",
                "max_results": 3,
                "time_range": "day",
            },
        )

        _, parameters = port.search.call_args.args
        assert parameters.categories == ("news",)
        assert parameters.engines == ("bing",)
        assert parameters.language == "de"
        assert parameters.max_results == 3
        assert parameters.time_range == "day"

    async def test_applies_defaults_for_omitted_arguments(self) -> None:
        """Omitted optional arguments fall back to defaults."""
        use_case, port = make_use_case()
        server = build_server(use_case)

        await call_tool(server, "web_search", {"query": "test"})

        _, parameters = port.search.call_args.args
        assert parameters.language == DEFAULT_LANGUAGE
        assert parameters.max_results == DEFAULT_MAX_RESULTS
        assert parameters.time_range is None

    @pytest.mark.parametrize(
        "arguments,expected",
        [
            ({}, "Missing required parameter"),
            ({"query": ""}, "Missing required parameter"),
            ({"query": "   "}, "Missing required parameter"),
            ({"query": 42}, "Missing required parameter"),
            ({"query": "t", "categories": "news"}, "must be an array of strings"),
            ({"query": "t", "engines": [1, 2]}, "must be an array of strings"),
            ({"query": "t", "max_results": "5"}, "must be an integer"),
            ({"query": "t", "max_results": True}, "must be an integer"),
            ({"query": "t", "max_results": 0}, "must be positive"),
            ({"query": "t", "max_results": -1}, "must be positive"),
            ({"query": "t", "max_results": 5.5}, "must be an integer"),
            ({"query": "t", "max_results": 500}, "cannot exceed 100"),
            ({"query": "t", "time_range": "decade"}, "Time range must be one of"),
            ({"query": "t", "language": 123}, "must be a non-empty string"),
            ({"query": "t", "language": True}, "must be a non-empty string"),
            ({"query": "t", "language": ""}, "must be a non-empty string"),
            ({"query": "t", "language": "   "}, "must be a non-empty string"),
            ({"query": "t", "language": ["en"]}, "must be a non-empty string"),
        ],
    )
    async def test_invalid_arguments_return_tool_error(
        self, arguments: dict[str, Any], expected: str
    ) -> None:
        """Bad arguments are reported to the model, not raised as protocol errors."""
        server = build_server(make_use_case()[0])

        result = await call_tool(server, "web_search", arguments)

        assert result.is_error is True
        assert expected in text_at(result, 0)

    async def test_search_failure_returns_tool_error(self) -> None:
        """A backend failure is surfaced as an error result the model can see."""
        use_case, _ = make_use_case(side_effect=SearchError("instance unreachable"))
        server = build_server(use_case)

        result = await call_tool(server, "web_search", {"query": "test"})

        assert result.is_error is True
        assert "instance unreachable" in text_at(result, 0)

    async def test_missing_arguments_object_is_handled(self) -> None:
        """A tools/call with no arguments is a tool error, not a crash."""
        server = build_server(make_use_case()[0])
        handler = handler_for(server, "tools/call")

        result = await handler(
            make_ctx(), CallToolRequestParams(name="web_search", arguments=None)
        )

        assert result.is_error is True


class TestServeFunction:
    """Test the serve() entry point."""

    async def test_serve_wires_adapter_and_runs_server(self) -> None:
        """serve() builds the adapter, runs the server, and cleans up."""
        from searxng.server import serve

        mock_adapter = Mock()
        streams = (Mock(), Mock())

        with (
            patch(
                "searxng.adapters.HttpSearchAdapter", return_value=mock_adapter
            ) as mock_adapter_cls,
            patch("searxng.server.stdio_server", new_callable=Mock) as mock_stdio,
            patch("searxng.server.build_server", new_callable=Mock) as mock_build,
        ):
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=streams)
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_build.return_value.run = AsyncMock()

            await serve(instance_url="https://custom.searx", timeout=45)

        mock_adapter_cls.assert_called_once_with(
            instance_url="https://custom.searx", timeout=45
        )
        mock_build.return_value.run.assert_awaited_once()
        mock_adapter.close.assert_called_once()

    async def test_serve_closes_adapter_on_failure(self) -> None:
        """The adapter is released even if the server loop raises."""
        from searxng.server import serve

        mock_adapter = Mock()

        with (
            patch("searxng.adapters.HttpSearchAdapter", return_value=mock_adapter),
            patch("searxng.server.stdio_server", new_callable=Mock) as mock_stdio,
            patch("searxng.server.build_server", new_callable=Mock) as mock_build,
        ):
            mock_stdio.return_value.__aenter__ = AsyncMock(
                return_value=(Mock(), Mock())
            )
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_build.return_value.run = AsyncMock(side_effect=RuntimeError("boom"))

            with pytest.raises(RuntimeError, match="boom"):
                await serve()

        mock_adapter.close.assert_called_once()

    async def test_serve_http_builds_streamable_http_app(self) -> None:
        """--transport http serves the Streamable HTTP ASGI app via uvicorn."""
        from searxng.server import STREAMABLE_HTTP_PATH, serve

        mock_adapter = Mock()
        mock_uvicorn = Mock()
        mock_uvicorn.Server.return_value.serve = AsyncMock()

        with (
            patch("searxng.adapters.HttpSearchAdapter", return_value=mock_adapter),
            patch("searxng.server.build_server", new_callable=Mock) as mock_build,
            patch.dict("sys.modules", {"uvicorn": mock_uvicorn}),
        ):
            await serve(transport="http", host="0.0.0.0", port=9123)

        mock_build.return_value.streamable_http_app.assert_called_once_with(
            streamable_http_path=STREAMABLE_HTTP_PATH, host="0.0.0.0"
        )
        config_kwargs = mock_uvicorn.Config.call_args.kwargs
        assert config_kwargs["host"] == "0.0.0.0"
        assert config_kwargs["port"] == 9123
        mock_uvicorn.Server.return_value.serve.assert_awaited_once()
        mock_adapter.close.assert_called_once()

    async def test_serve_http_does_not_use_stdio(self) -> None:
        """The http transport must not also grab stdin/stdout."""
        from searxng.server import serve

        mock_uvicorn = Mock()
        mock_uvicorn.Server.return_value.serve = AsyncMock()

        with (
            patch("searxng.adapters.HttpSearchAdapter", return_value=Mock()),
            patch("searxng.server.build_server", new_callable=Mock),
            patch("searxng.server.stdio_server", new_callable=Mock) as mock_stdio,
            patch.dict("sys.modules", {"uvicorn": mock_uvicorn}),
        ):
            await serve(transport="http")

        mock_stdio.assert_not_called()

    @pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "example.com"])
    async def test_serve_http_warns_on_public_bind(
        self, host: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A non-loopback bind loses DNS-rebinding protection; say so."""
        from searxng.server import serve

        mock_uvicorn = Mock()
        mock_uvicorn.Server.return_value.serve = AsyncMock()

        with (
            patch("searxng.adapters.HttpSearchAdapter", return_value=Mock()),
            patch("searxng.server.build_server", new_callable=Mock),
            patch.dict("sys.modules", {"uvicorn": mock_uvicorn}),
            caplog.at_level(logging.WARNING, logger="searxng.server"),
        ):
            await serve(transport="http", host=host)

        assert "without authentication" in caplog.text
        assert host in caplog.text

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
    async def test_serve_http_quiet_on_loopback_bind(
        self, host: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Loopback binds keep DNS-rebinding protection, so no warning."""
        from searxng.server import serve

        mock_uvicorn = Mock()
        mock_uvicorn.Server.return_value.serve = AsyncMock()

        with (
            patch("searxng.adapters.HttpSearchAdapter", return_value=Mock()),
            patch("searxng.server.build_server", new_callable=Mock),
            patch.dict("sys.modules", {"uvicorn": mock_uvicorn}),
            caplog.at_level(logging.WARNING, logger="searxng.server"),
        ):
            await serve(transport="http", host=host)

        assert "without authentication" not in caplog.text

    async def test_serve_stdio_does_not_warn(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The stdio transport is not network-exposed, so it never warns."""
        from searxng.server import serve

        with (
            patch("searxng.adapters.HttpSearchAdapter", return_value=Mock()),
            patch("searxng.server.stdio_server", new_callable=Mock) as mock_stdio,
            patch("searxng.server.build_server", new_callable=Mock) as mock_build,
            caplog.at_level(logging.WARNING, logger="searxng.server"),
        ):
            mock_stdio.return_value.__aenter__ = AsyncMock(
                return_value=(Mock(), Mock())
            )
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_build.return_value.run = AsyncMock()

            await serve()

        assert "without authentication" not in caplog.text

    @pytest.mark.parametrize("transport", ["sse", "websocket", "", "STDIO"])
    async def test_serve_rejects_unknown_transport(self, transport: str) -> None:
        """An unsupported transport fails fast, before any adapter is built."""
        from searxng.server import serve

        with (
            patch("searxng.adapters.HttpSearchAdapter") as mock_adapter_cls,
            pytest.raises(ValueError, match="Transport must be one of"),
        ):
            await serve(transport=transport)

        mock_adapter_cls.assert_not_called()

    async def test_serve_closes_adapter_when_http_fails(self) -> None:
        """The adapter is released if the HTTP server loop raises."""
        from searxng.server import serve

        mock_adapter = Mock()
        mock_uvicorn = Mock()
        mock_uvicorn.Server.return_value.serve = AsyncMock(
            side_effect=RuntimeError("bind failed")
        )

        with (
            patch("searxng.adapters.HttpSearchAdapter", return_value=mock_adapter),
            patch("searxng.server.build_server", new_callable=Mock),
            patch.dict("sys.modules", {"uvicorn": mock_uvicorn}),
            pytest.raises(RuntimeError, match="bind failed"),
        ):
            await serve(transport="http")

        mock_adapter.close.assert_called_once()
