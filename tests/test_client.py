"""Tests for domain layer (client module)."""

import pytest

from searxng.client import (
    ResultIndex,
    SearchParameters,
    SearchQuery,
    SearchResult,
    SearchResultCollection,
    SearchResultContent,
    SearchResultTitle,
    SearchResultUrl,
)


class TestSearchQuery:
    """Test SearchQuery value object."""

    def test_creates_valid_query(self) -> None:
        """Test creating a valid search query."""
        query = SearchQuery(text="Python programming")
        assert query.text == "Python programming"

    def test_rejects_empty_query(self) -> None:
        """Test that empty queries are rejected."""
        with pytest.raises(ValueError, match="Search query cannot be empty"):
            SearchQuery(text="")

    def test_rejects_whitespace_only_query(self) -> None:
        """Test that whitespace-only queries are rejected."""
        with pytest.raises(ValueError, match="Search query cannot be empty"):
            SearchQuery(text="   ")


class TestSearchResultUrl:
    """Test SearchResultUrl value object."""

    def test_creates_valid_url(self) -> None:
        """Test creating a valid URL."""
        url = SearchResultUrl(value="https://example.com")
        assert url.value == "https://example.com"

    def test_creates_empty_url(self) -> None:
        """Test creating an empty URL is allowed."""
        url = SearchResultUrl(value="")
        assert url.value == ""


class TestSearchResultTitle:
    """Test SearchResultTitle value object."""

    def test_creates_valid_title(self) -> None:
        """Test creating a valid title."""
        title = SearchResultTitle(value="Example Title")
        assert title.value == "Example Title"

    def test_creates_empty_title(self) -> None:
        """Test creating an empty title is allowed."""
        title = SearchResultTitle(value="")
        assert title.value == ""


class TestSearchResultContent:
    """Test SearchResultContent value object."""

    def test_creates_valid_content(self) -> None:
        """Test creating valid content."""
        content = SearchResultContent(value="Some content here")
        assert content.value == "Some content here"

    def test_creates_empty_content(self) -> None:
        """Test creating empty content is allowed."""
        content = SearchResultContent(value="")
        assert content.value == ""


class TestResultIndex:
    """Test ResultIndex value object."""

    def test_creates_valid_index(self) -> None:
        """Test creating a valid index."""
        index = ResultIndex(value=5)
        assert index.value == 5

    def test_creates_zero_index(self) -> None:
        """Test creating index with zero."""
        index = ResultIndex(value=0)
        assert index.value == 0

    def test_rejects_negative_index(self) -> None:
        """Test that negative indices are rejected."""
        with pytest.raises(ValueError, match="Index cannot be negative"):
            ResultIndex(value=-1)


class TestSearchResult:
    """Test SearchResult entity."""

    def test_creates_valid_result(self) -> None:
        """Test creating a valid search result."""
        result = SearchResult(
            index=ResultIndex(value=0),
            title=SearchResultTitle(value="Test Title"),
            url=SearchResultUrl(value="https://test.com"),
            content=SearchResultContent(value="Test content"),
        )
        assert result.index.value == 0
        assert result.title.value == "Test Title"
        assert result.url.value == "https://test.com"
        assert result.content.value == "Test content"


class TestSearchParameters:
    """Test SearchParameters value object."""

    def test_creates_valid_parameters(self) -> None:
        """Test creating valid search parameters."""
        params = SearchParameters(
            categories=("general", "news"),
            engines=("google", "bing"),
            language="en",
            max_results=10,
            time_range="week",
        )
        assert params.categories == ("general", "news")
        assert params.engines == ("google", "bing")
        assert params.language == "en"
        assert params.max_results == 10
        assert params.time_range == "week"

    def test_creates_parameters_without_time_range(self) -> None:
        """Test creating parameters without time range."""
        params = SearchParameters(
            categories=("general",),
            engines=("duckduckgo",),
            language="en",
            max_results=5,
            time_range=None,
        )
        assert params.time_range is None

    def test_rejects_zero_max_results(self) -> None:
        """Test that zero max results is rejected."""
        with pytest.raises(ValueError, match="Max results must be positive"):
            SearchParameters(
                categories=(),
                engines=(),
                language="en",
                max_results=0,
                time_range=None,
            )

    def test_rejects_negative_max_results(self) -> None:
        """Test that negative max results is rejected."""
        with pytest.raises(ValueError, match="Max results must be positive"):
            SearchParameters(
                categories=(),
                engines=(),
                language="en",
                max_results=-5,
                time_range=None,
            )


class TestSearchResultCollection:
    """Test SearchResultCollection first-class collection."""

    def test_creates_empty_collection(self) -> None:
        """Test creating an empty collection."""
        query = SearchQuery(text="test")
        collection = SearchResultCollection(query=query, results=())
        assert collection.query.text == "test"
        assert len(collection.results) == 0

    def test_creates_collection_with_results(self) -> None:
        """Test creating a collection with results."""
        query = SearchQuery(text="test")
        results = (
            SearchResult(
                index=ResultIndex(value=0),
                title=SearchResultTitle(value="Title 1"),
                url=SearchResultUrl(value="https://example1.com"),
                content=SearchResultContent(value="Content 1"),
            ),
            SearchResult(
                index=ResultIndex(value=1),
                title=SearchResultTitle(value="Title 2"),
                url=SearchResultUrl(value="https://example2.com"),
                content=SearchResultContent(value="Content 2"),
            ),
        )
        collection = SearchResultCollection(query=query, results=results)
        assert len(collection.results) == 2

    def test_formats_empty_collection_as_text(self) -> None:
        """Test formatting empty collection."""
        query = SearchQuery(text="test")
        collection = SearchResultCollection(query=query, results=())
        formatted = collection.format_as_text()
        assert formatted == []

    def test_formats_collection_as_text(self) -> None:
        """Test formatting collection with results as text."""
        query = SearchQuery(text="test")
        results = (
            SearchResult(
                index=ResultIndex(value=0),
                title=SearchResultTitle(value="Title 1"),
                url=SearchResultUrl(value="https://example1.com"),
                content=SearchResultContent(value="Content 1"),
            ),
            SearchResult(
                index=ResultIndex(value=1),
                title=SearchResultTitle(value="Title 2"),
                url=SearchResultUrl(value="https://example2.com"),
                content=SearchResultContent(value="Content 2"),
            ),
        )
        collection = SearchResultCollection(query=query, results=results)
        formatted = collection.format_as_text()

        assert len(formatted) == 2
        assert "[0] Title 1" in formatted[0]
        assert "URL: https://example1.com" in formatted[0]
        assert "Content 1" in formatted[0]
        assert "[1] Title 2" in formatted[1]
        assert "URL: https://example2.com" in formatted[1]
        assert "Content 2" in formatted[1]
