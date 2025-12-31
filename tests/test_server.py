"""Tests for application layer (server module)."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from searxng.client import (
    SearchParameters,
    SearchQuery,
    SearchResultCollection,
)
from searxng.server import (
    DEFAULT_CATEGORIES,
    DEFAULT_ENGINES,
    SearchUseCase,
)


class TestSearchUseCase:
    """Test SearchUseCase application service."""

    @pytest.mark.asyncio
    async def test_execute_with_all_parameters(self) -> None:
        """Test executing search with all parameters."""
        mock_port = Mock()
        query = SearchQuery(text="test query")
        expected_collection = SearchResultCollection(query=query, results=())
        mock_port.search.return_value = expected_collection

        use_case = SearchUseCase(search_port=mock_port)

        result = await use_case.execute(
            query_text="test query",
            categories=("general", "news"),
            engines=("google", "bing"),
            language="en",
            max_results=15,
            time_range="week",
        )

        mock_port.search.assert_called_once()
        call_args = mock_port.search.call_args
        assert call_args[0][0].text == "test query"
        assert call_args[0][1].categories == ("general", "news")
        assert call_args[0][1].engines == ("google", "bing")
        assert call_args[0][1].language == "en"
        assert call_args[0][1].max_results == 15
        assert call_args[0][1].time_range == "week"
        assert result == expected_collection

    @pytest.mark.asyncio
    async def test_execute_with_defaults(self) -> None:
        """Test executing search with default parameters."""
        mock_port = Mock()
        query = SearchQuery(text="test")
        expected_collection = SearchResultCollection(query=query, results=())
        mock_port.search.return_value = expected_collection

        use_case = SearchUseCase(search_port=mock_port)

        result = await use_case.execute(
            query_text="test",
            categories=None,
            engines=None,
            language="en",
            max_results=10,
            time_range=None,
        )

        mock_port.search.assert_called_once()
        call_args = mock_port.search.call_args
        assert call_args[0][1].categories == DEFAULT_CATEGORIES
        assert call_args[0][1].engines == DEFAULT_ENGINES
        assert call_args[0][1].time_range is None
        assert result == expected_collection

    @pytest.mark.asyncio
    async def test_execute_creates_valid_search_query(self) -> None:
        """Test that execute creates valid SearchQuery."""
        mock_port = Mock()
        query = SearchQuery(text="Python programming")
        expected_collection = SearchResultCollection(query=query, results=())
        mock_port.search.return_value = expected_collection

        use_case = SearchUseCase(search_port=mock_port)

        await use_case.execute(
            query_text="Python programming",
            categories=None,
            engines=None,
            language="en",
            max_results=10,
            time_range=None,
        )

        call_args = mock_port.search.call_args
        assert isinstance(call_args[0][0], SearchQuery)
        assert call_args[0][0].text == "Python programming"

    @pytest.mark.asyncio
    async def test_execute_creates_valid_search_parameters(self) -> None:
        """Test that execute creates valid SearchParameters."""
        mock_port = Mock()
        query = SearchQuery(text="test")
        expected_collection = SearchResultCollection(query=query, results=())
        mock_port.search.return_value = expected_collection

        use_case = SearchUseCase(search_port=mock_port)

        await use_case.execute(
            query_text="test",
            categories=("images",),
            engines=("duckduckgo",),
            language="fr",
            max_results=20,
            time_range="day",
        )

        call_args = mock_port.search.call_args
        assert isinstance(call_args[0][1], SearchParameters)
        assert call_args[0][1].categories == ("images",)
        assert call_args[0][1].engines == ("duckduckgo",)
        assert call_args[0][1].language == "fr"
        assert call_args[0][1].max_results == 20
        assert call_args[0][1].time_range == "day"

    @pytest.mark.asyncio
    async def test_execute_with_empty_tuples_uses_defaults(self) -> None:
        """Test that empty tuples are passed through."""
        mock_port = Mock()
        query = SearchQuery(text="test")
        expected_collection = SearchResultCollection(query=query, results=())
        mock_port.search.return_value = expected_collection

        use_case = SearchUseCase(search_port=mock_port)

        await use_case.execute(
            query_text="test",
            categories=(),
            engines=(),
            language="en",
            max_results=10,
            time_range=None,
        )

        call_args = mock_port.search.call_args
        # Empty tuples get defaults when None or empty
        assert call_args[0][1].categories == DEFAULT_CATEGORIES
        assert call_args[0][1].engines == DEFAULT_ENGINES


class TestServeFunction:
    """Test the serve function and MCP server setup."""

    @pytest.mark.asyncio
    async def test_serve_initializes_server(self) -> None:
        """Test that serve initializes the MCP server correctly."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.server.stdio_server") as mock_stdio,
            patch("searxng.adapters.HttpSearchAdapter"),
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            # Mock stdio_server context manager
            mock_read_stream = Mock()
            mock_write_stream = Mock()
            mock_stdio.return_value.__aenter__ = AsyncMock(
                return_value=(mock_read_stream, mock_write_stream)
            )
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock server.run to avoid hanging
            mock_server_instance.run = AsyncMock()
            mock_server_instance.create_initialization_options = Mock(return_value={})

            from searxng.server import serve

            await serve(instance_url="https://test.searx")

            mock_server_class.assert_called_once_with("SearXNGServer")

    @pytest.mark.asyncio
    async def test_list_resources_handler(self) -> None:
        """Test the list_resources handler."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.adapters.HttpSearchAdapter"),
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            # Capture the decorated function
            list_resources_func = None

            def capture_list_resources():
                def decorator(func):
                    nonlocal list_resources_func
                    list_resources_func = func
                    return func

                return decorator

            mock_server_instance.list_resources = capture_list_resources

            from searxng.server import serve

            # Initialize the server setup (without running)
            with patch("searxng.server.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(Mock(), Mock())
                )
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_server_instance.run = AsyncMock()
                mock_server_instance.create_initialization_options = Mock(
                    return_value={}
                )

                await serve()

            # Test the captured handler
            if list_resources_func:
                resources = await list_resources_func()
                assert len(resources) == 1
                assert resources[0]["uri"] == "searxng://web/search"
                assert resources[0]["name"] == "Web Search"

    @pytest.mark.asyncio
    async def test_read_resource_handler_valid_uri(self) -> None:
        """Test the read_resource handler with valid URI."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.adapters.HttpSearchAdapter"),
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            read_resource_func = None

            def capture_read_resource():
                def decorator(func):
                    nonlocal read_resource_func
                    read_resource_func = func
                    return func

                return decorator

            mock_server_instance.read_resource = capture_read_resource

            from searxng.server import serve

            with patch("searxng.server.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(Mock(), Mock())
                )
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_server_instance.run = AsyncMock()
                mock_server_instance.create_initialization_options = Mock(
                    return_value={}
                )

                await serve()

            if read_resource_func:
                from pydantic import AnyUrl

                result = await read_resource_func(AnyUrl("searxng://test"))
                assert '"message"' in result
                assert "not yet implemented" in result

    @pytest.mark.asyncio
    async def test_read_resource_handler_invalid_uri(self) -> None:
        """Test the read_resource handler with invalid URI."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.adapters.HttpSearchAdapter"),
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            read_resource_func = None

            def capture_read_resource():
                def decorator(func):
                    nonlocal read_resource_func
                    read_resource_func = func
                    return func

                return decorator

            mock_server_instance.read_resource = capture_read_resource

            from searxng.server import serve

            with patch("searxng.server.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(Mock(), Mock())
                )
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_server_instance.run = AsyncMock()
                mock_server_instance.create_initialization_options = Mock(
                    return_value={}
                )

                await serve()

            if read_resource_func:
                from pydantic import AnyUrl

                with pytest.raises(ValueError, match="Unsupported URI"):
                    await read_resource_func(AnyUrl("http://invalid"))

    @pytest.mark.asyncio
    async def test_list_tools_handler(self) -> None:
        """Test the list_tools handler."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.adapters.HttpSearchAdapter"),
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            list_tools_func = None

            def capture_list_tools():
                def decorator(func):
                    nonlocal list_tools_func
                    list_tools_func = func
                    return func

                return decorator

            mock_server_instance.list_tools = capture_list_tools

            from searxng.server import serve

            with patch("searxng.server.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(Mock(), Mock())
                )
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_server_instance.run = AsyncMock()
                mock_server_instance.create_initialization_options = Mock(
                    return_value={}
                )

                await serve()

            if list_tools_func:
                tools = await list_tools_func()
                assert len(tools) == 1
                assert tools[0].name == "web_search"
                assert "SearXNG" in tools[0].description

    @pytest.mark.asyncio
    async def test_call_tool_unsupported_tool(self) -> None:
        """Test call_tool with unsupported tool name."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.adapters.HttpSearchAdapter"),
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            call_tool_func = None

            def capture_call_tool():
                def decorator(func):
                    nonlocal call_tool_func
                    call_tool_func = func
                    return func

                return decorator

            mock_server_instance.call_tool = capture_call_tool

            from searxng.server import serve

            with patch("searxng.server.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(Mock(), Mock())
                )
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_server_instance.run = AsyncMock()
                mock_server_instance.create_initialization_options = Mock(
                    return_value={}
                )

                await serve()

            if call_tool_func:
                result = await call_tool_func(name="unsupported_tool", arguments={})
                assert len(result) == 1
                assert "Unsupported tool" in result[0].text

    @pytest.mark.asyncio
    async def test_web_search_tool_successful(self) -> None:
        """Test successful web search execution."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.adapters.HttpSearchAdapter") as mock_adapter_class,
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            mock_adapter = Mock()
            mock_adapter_class.return_value = mock_adapter

            # Mock search result
            from searxng.client import (
                ResultIndex,
                SearchQuery,
                SearchResult,
                SearchResultCollection,
                SearchResultContent,
                SearchResultTitle,
                SearchResultUrl,
            )

            query = SearchQuery(text="test")
            result = SearchResult(
                index=ResultIndex(value=0),
                title=SearchResultTitle(value="Test"),
                url=SearchResultUrl(value="https://test.com"),
                content=SearchResultContent(value="Test content"),
            )
            collection = SearchResultCollection(query=query, results=(result,))
            mock_adapter.search.return_value = collection

            call_tool_func = None

            def capture_call_tool():
                def decorator(func):
                    nonlocal call_tool_func
                    call_tool_func = func
                    return func

                return decorator

            mock_server_instance.call_tool = capture_call_tool

            from searxng.server import serve

            with patch("searxng.server.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(Mock(), Mock())
                )
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_server_instance.run = AsyncMock()
                mock_server_instance.create_initialization_options = Mock(
                    return_value={}
                )
                mock_server_instance.list_resources = lambda: lambda f: f
                mock_server_instance.read_resource = lambda: lambda f: f
                mock_server_instance.list_tools = lambda: lambda f: f

                await serve()

            if call_tool_func:
                result = await call_tool_func(
                    name="web_search", arguments={"query": "test"}
                )
                assert len(result) > 0

    @pytest.mark.asyncio
    async def test_web_search_tool_missing_query(self) -> None:
        """Test web search with missing query parameter."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.adapters.HttpSearchAdapter"),
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            call_tool_func = None

            def capture_call_tool():
                def decorator(func):
                    nonlocal call_tool_func
                    call_tool_func = func
                    return func

                return decorator

            mock_server_instance.call_tool = capture_call_tool

            from searxng.server import serve

            with patch("searxng.server.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(Mock(), Mock())
                )
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_server_instance.run = AsyncMock()
                mock_server_instance.create_initialization_options = Mock(
                    return_value={}
                )
                mock_server_instance.list_resources = lambda: lambda f: f
                mock_server_instance.read_resource = lambda: lambda f: f
                mock_server_instance.list_tools = lambda: lambda f: f

                await serve()

            if call_tool_func:
                from mcp.shared.exceptions import McpError

                with pytest.raises((ValueError, McpError)):
                    await call_tool_func(name="web_search", arguments={})

    @pytest.mark.asyncio
    async def test_web_search_tool_with_exception(self) -> None:
        """Test web search handling exceptions."""
        with (
            patch("searxng.server.Server") as mock_server_class,
            patch("searxng.adapters.HttpSearchAdapter") as mock_adapter_class,
        ):
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance

            mock_adapter = Mock()
            mock_adapter_class.return_value = mock_adapter
            mock_adapter.search.side_effect = Exception("Test error")

            call_tool_func = None

            def capture_call_tool():
                def decorator(func):
                    nonlocal call_tool_func
                    call_tool_func = func
                    return func

                return decorator

            mock_server_instance.call_tool = capture_call_tool

            from searxng.server import serve

            with patch("searxng.server.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(Mock(), Mock())
                )
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_server_instance.run = AsyncMock()
                mock_server_instance.create_initialization_options = Mock(
                    return_value={}
                )
                mock_server_instance.list_resources = lambda: lambda f: f
                mock_server_instance.read_resource = lambda: lambda f: f
                mock_server_instance.list_tools = lambda: lambda f: f

                await serve()

            if call_tool_func:
                from mcp.shared.exceptions import McpError

                with pytest.raises(McpError):
                    await call_tool_func(name="web_search", arguments={"query": "test"})
