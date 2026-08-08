"""Tests for infrastructure adapters."""

from unittest.mock import Mock, patch

import pytest
import requests

from searxng.adapters import (
    HttpSearchAdapter,
    InstanceUrl,
    SearchTimeout,
)
from searxng.client import (
    SearchParameters,
    SearchQuery,
)


class TestInstanceUrl:
    """Test InstanceUrl value object."""

    def test_creates_valid_url(self) -> None:
        """Test creating a valid instance URL."""
        url = InstanceUrl(value="https://searx.party")
        assert url.value == "https://searx.party"

    def test_rejects_empty_url(self) -> None:
        """Test that empty URLs are rejected."""
        with pytest.raises(ValueError, match="Instance URL cannot be empty"):
            InstanceUrl(value="")


class TestSearchTimeout:
    """Test SearchTimeout value object."""

    def test_creates_valid_timeout(self) -> None:
        """Test creating a valid timeout."""
        timeout = SearchTimeout(seconds=30)
        assert timeout.seconds == 30

    def test_rejects_zero_timeout(self) -> None:
        """Test that zero timeout is rejected."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            SearchTimeout(seconds=0)

    def test_rejects_negative_timeout(self) -> None:
        """Test that negative timeout is rejected."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            SearchTimeout(seconds=-5)


class TestHttpSearchAdapter:
    """Test HttpSearchAdapter infrastructure adapter."""

    def test_initializes_with_defaults(self) -> None:
        """Test adapter initialization with defaults."""
        adapter = HttpSearchAdapter()
        assert adapter._instance_url.value == "https://searx.party"
        assert adapter._timeout.seconds == 30

    def test_initializes_with_custom_values(self) -> None:
        """Test adapter initialization with custom values."""
        adapter = HttpSearchAdapter(instance_url="https://custom.searx", timeout=60)
        assert adapter._instance_url.value == "https://custom.searx"
        assert adapter._timeout.seconds == 60

    @patch("searxng.adapters.requests.get")
    async def test_successful_search(self, mock_get: Mock) -> None:
        """Test successful search operation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://test.com",
                    "content": "Test content",
                }
            ]
        }
        mock_get.return_value = mock_response

        adapter = HttpSearchAdapter()
        query = SearchQuery(text="test query")
        parameters = SearchParameters(
            categories=("general",),
            engines=("google",),
            language="en",
            max_results=10,
            time_range=None,
        )

        result = await adapter.search(query, parameters)

        assert result.query.text == "test query"
        assert len(result.results) == 1
        assert result.results[0].title.value == "Test Result"
        assert result.results[0].url.value == "https://test.com"
        assert result.results[0].content.value == "Test content"

    @patch("searxng.adapters.requests.get")
    async def test_search_with_time_range(self, mock_get: Mock) -> None:
        """Test search with time range parameter."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        adapter = HttpSearchAdapter()
        query = SearchQuery(text="recent news")
        parameters = SearchParameters(
            categories=("news",),
            engines=("bing",),
            language="en",
            max_results=5,
            time_range="week",
        )

        result = await adapter.search(query, parameters)

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]["params"]["time_range"] == "week"
        assert result.query.text == "recent news"

    @patch("searxng.adapters.requests.get")
    async def test_search_respects_max_results(self, mock_get: Mock) -> None:
        """Test that search respects max_results parameter."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": f"Result {i}",
                    "url": f"https://example{i}.com",
                    "content": f"Content {i}",
                }
                for i in range(10)
            ]
        }
        mock_get.return_value = mock_response

        adapter = HttpSearchAdapter()
        query = SearchQuery(text="test")
        parameters = SearchParameters(
            categories=("general",),
            engines=("google",),
            language="en",
            max_results=3,
            time_range=None,
        )

        result = await adapter.search(query, parameters)

        assert len(result.results) == 3

    @patch("searxng.adapters.requests.get")
    async def test_search_handles_empty_results(self, mock_get: Mock) -> None:
        """Test handling of empty search results."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        adapter = HttpSearchAdapter()
        query = SearchQuery(text="nonexistent query")
        parameters = SearchParameters(
            categories=("general",),
            engines=("google",),
            language="en",
            max_results=10,
            time_range=None,
        )

        result = await adapter.search(query, parameters)

        assert len(result.results) == 0

    @patch("searxng.adapters.requests.get")
    async def test_search_handles_request_exception(self, mock_get: Mock) -> None:
        """Test handling of request exceptions."""
        mock_get.side_effect = requests.RequestException("Network error")

        adapter = HttpSearchAdapter()
        query = SearchQuery(text="test")
        parameters = SearchParameters(
            categories=("general",),
            engines=("google",),
            language="en",
            max_results=10,
            time_range=None,
        )

        result = await adapter.search(query, parameters)

        assert len(result.results) == 0

    @patch("searxng.adapters.requests.get")
    async def test_search_handles_missing_fields(self, mock_get: Mock) -> None:
        """Test handling of results with missing fields."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Only Title"},
                {"url": "https://only-url.com"},
                {},
            ]
        }
        mock_get.return_value = mock_response

        adapter = HttpSearchAdapter()
        query = SearchQuery(text="test")
        parameters = SearchParameters(
            categories=("general",),
            engines=("google",),
            language="en",
            max_results=10,
            time_range=None,
        )

        result = await adapter.search(query, parameters)

        assert len(result.results) == 3
        assert result.results[0].title.value == "Only Title"
        assert result.results[0].url.value == ""
        assert result.results[1].url.value == "https://only-url.com"

    @patch("searxng.adapters.requests.get")
    async def test_build_request_params_with_all_options(self, mock_get: Mock) -> None:
        """Test building request parameters with all options."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        adapter = HttpSearchAdapter()
        query = SearchQuery(text="test query")
        parameters = SearchParameters(
            categories=("general", "news"),
            engines=("google", "bing", "duckduckgo"),
            language="fr",
            max_results=15,
            time_range="month",
        )

        await adapter.search(query, parameters)

        call_args = mock_get.call_args
        params = call_args[1]["params"]

        assert params["q"] == "test query"
        assert params["categories"] == "general,news"
        assert params["engines"] == "google,bing,duckduckgo"
        assert params["language"] == "fr"
        assert params["time_range"] == "month"
        assert params["format"] == "json"
        assert params["safesearch"] == 1
        assert params["pageno"] == 1

    @patch("searxng.adapters.requests.get")
    async def test_build_request_params_without_optional_fields(
        self, mock_get: Mock
    ) -> None:
        """Test building request parameters without optional fields."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        adapter = HttpSearchAdapter()
        query = SearchQuery(text="simple")
        parameters = SearchParameters(
            categories=(),
            engines=(),
            language="en",
            max_results=10,
            time_range=None,
        )

        await adapter.search(query, parameters)

        call_args = mock_get.call_args
        params = call_args[1]["params"]

        assert "categories" not in params
        assert "engines" not in params
        assert "time_range" not in params

    @patch("searxng.adapters.requests.get")
    async def test_execute_request_uses_correct_timeout(self, mock_get: Mock) -> None:
        """Test that request uses correct timeout value."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        adapter = HttpSearchAdapter(timeout=45)
        query = SearchQuery(text="test")
        parameters = SearchParameters(
            categories=("general",),
            engines=("google",),
            language="en",
            max_results=10,
            time_range=None,
        )

        await adapter.search(query, parameters)

        call_args = mock_get.call_args
        assert call_args[1]["timeout"] == 45
