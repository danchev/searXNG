"""Tests for infrastructure adapters."""

from typing import Any
from unittest.mock import Mock

import pytest
import requests

from searxng.adapters import (
    HttpSearchAdapter,
    InstanceUrl,
    SearchTimeout,
)
from searxng.client import (
    SearchError,
    SearchParameters,
    SearchQuery,
)


def make_parameters(
    categories: tuple[str, ...] = ("general",),
    engines: tuple[str, ...] = ("google",),
    language: str = "en",
    max_results: int = 10,
    time_range: str | None = None,
) -> SearchParameters:
    """Build SearchParameters with sensible test defaults."""
    return SearchParameters(
        categories=categories,
        engines=engines,
        language=language,
        max_results=max_results,
        time_range=time_range,
    )


def make_session(payload: Any = None, side_effect: Exception | None = None) -> Mock:
    """Build a mock requests.Session returning the given JSON payload."""
    session = Mock(spec=requests.Session)
    if side_effect is not None:
        session.get.side_effect = side_effect
        return session

    response = Mock()
    response.json.return_value = {"results": []} if payload is None else payload
    session.get.return_value = response
    return session


def sent_params(session: Mock) -> dict[str, Any]:
    """Extract the query params from the mock session's last call."""
    return session.get.call_args.kwargs["params"]


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

    def test_rejects_whitespace_only_url(self) -> None:
        """A URL that is only whitespace is treated as empty."""
        with pytest.raises(ValueError, match="Instance URL cannot be empty"):
            InstanceUrl(value="   ")

    @pytest.mark.parametrize(
        "value",
        ["https://searx.party ", " https://searx.party", "\thttps://searx.party\n"],
    )
    def test_rejects_surrounding_whitespace(self, value: str) -> None:
        """Leading/trailing whitespace is rejected rather than silently kept.

        ``requests`` tolerates a stray leading space in a URL, so without this
        check a misconfigured --instance-url would silently work most of the
        time and fail unpredictably elsewhere.
        """
        with pytest.raises(ValueError, match="leading or trailing whitespace"):
            InstanceUrl(value=value)

    @pytest.mark.parametrize(
        "value", ["searx.party", "ftp://searx.party", "https://", "not a url"]
    )
    def test_rejects_non_http_url(self, value: str) -> None:
        """Test that non-absolute or non-http(s) URLs are rejected."""
        with pytest.raises(ValueError, match="absolute http"):
            InstanceUrl(value=value)

    def test_strips_trailing_slash(self) -> None:
        """Trailing slashes are normalised so paths join cleanly."""
        assert InstanceUrl(value="https://searx.party/").value == "https://searx.party"


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

    @pytest.mark.parametrize("value", [True, False])
    def test_rejects_bool_timeout(self, value: bool) -> None:
        """bool is an int subclass but is never a meaningful timeout."""
        with pytest.raises(ValueError, match="not a bool"):
            SearchTimeout(seconds=value)

    def test_accepts_fractional_timeout(self) -> None:
        """requests supports fractional second timeouts; so do we."""
        assert SearchTimeout(seconds=1.5).seconds == 1.5


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

    async def test_successful_search(self) -> None:
        """Test successful search operation."""
        session = make_session(
            {
                "results": [
                    {
                        "title": "Test Result",
                        "url": "https://test.com",
                        "content": "Test content",
                    }
                ]
            }
        )
        adapter = HttpSearchAdapter(session=session)

        result = await adapter.search(SearchQuery(text="test query"), make_parameters())

        assert result.query.text == "test query"
        assert len(result.results) == 1
        assert result.results[0].title.value == "Test Result"
        assert result.results[0].url.value == "https://test.com"
        assert result.results[0].content.value == "Test content"

    async def test_search_targets_the_search_endpoint(self) -> None:
        """The adapter requests <instance>/search."""
        session = make_session()
        adapter = HttpSearchAdapter(
            instance_url="https://custom.searx/", session=session
        )

        await adapter.search(SearchQuery(text="test"), make_parameters())

        assert session.get.call_args.args[0] == "https://custom.searx/search"

    async def test_search_with_time_range(self) -> None:
        """Test search with time range parameter."""
        session = make_session()
        adapter = HttpSearchAdapter(session=session)

        result = await adapter.search(
            SearchQuery(text="recent news"),
            make_parameters(
                categories=("news",),
                engines=("bing",),
                max_results=5,
                time_range="week",
            ),
        )

        session.get.assert_called_once()
        assert sent_params(session)["time_range"] == "week"
        assert result.query.text == "recent news"

    async def test_search_respects_max_results(self) -> None:
        """Test that search respects max_results parameter."""
        session = make_session(
            {
                "results": [
                    {
                        "title": f"Result {i}",
                        "url": f"https://example{i}.com",
                        "content": f"Content {i}",
                    }
                    for i in range(10)
                ]
            }
        )
        adapter = HttpSearchAdapter(session=session)

        result = await adapter.search(
            SearchQuery(text="test"), make_parameters(max_results=3)
        )

        assert len(result.results) == 3

    async def test_search_handles_empty_results(self) -> None:
        """Test handling of empty search results."""
        adapter = HttpSearchAdapter(session=make_session({"results": []}))

        result = await adapter.search(SearchQuery(text="nope"), make_parameters())

        assert len(result.results) == 0

    async def test_search_raises_on_request_exception(self) -> None:
        """A network failure surfaces as SearchError, not as empty results."""
        session = make_session(side_effect=requests.RequestException("Network error"))
        adapter = HttpSearchAdapter(session=session)

        with pytest.raises(SearchError, match="Search request failed"):
            await adapter.search(SearchQuery(text="test"), make_parameters())

    async def test_search_raises_on_timeout(self) -> None:
        """A timeout reports the configured limit."""
        session = make_session(side_effect=requests.Timeout("too slow"))
        adapter = HttpSearchAdapter(timeout=45, session=session)

        with pytest.raises(SearchError, match="timed out after 45s"):
            await adapter.search(SearchQuery(text="test"), make_parameters())

    async def test_search_raises_on_non_json_body(self) -> None:
        """A non-JSON response body surfaces as SearchError."""
        session = make_session()
        session.get.return_value.json.side_effect = ValueError("not json")
        adapter = HttpSearchAdapter(session=session)

        with pytest.raises(SearchError, match="Invalid response"):
            await adapter.search(SearchQuery(text="test"), make_parameters())

    async def test_search_raises_on_json_that_is_not_an_object(self) -> None:
        """A JSON array instead of an object is rejected."""
        adapter = HttpSearchAdapter(session=make_session([1, 2, 3]))

        with pytest.raises(SearchError, match="Invalid response"):
            await adapter.search(SearchQuery(text="test"), make_parameters())

    async def test_search_raises_on_http_error(self) -> None:
        """A non-2xx status surfaces as SearchError."""
        session = make_session()
        session.get.return_value.raise_for_status.side_effect = requests.HTTPError(
            "429 Too Many Requests"
        )
        adapter = HttpSearchAdapter(session=session)

        with pytest.raises(SearchError, match="Search request failed"):
            await adapter.search(SearchQuery(text="test"), make_parameters())

    async def test_search_handles_missing_fields(self) -> None:
        """Test handling of results with missing fields."""
        session = make_session(
            {
                "results": [
                    {"title": "Only Title"},
                    {"url": "https://only-url.com"},
                    {},
                ]
            }
        )
        adapter = HttpSearchAdapter(session=session)

        result = await adapter.search(SearchQuery(text="test"), make_parameters())

        assert len(result.results) == 3
        assert result.results[0].title.value == "Only Title"
        assert result.results[0].url.value == ""
        assert result.results[1].url.value == "https://only-url.com"

    async def test_search_coerces_non_string_fields(self) -> None:
        """Null and non-string field values do not crash mapping."""
        session = make_session(
            {"results": [{"title": None, "url": 42, "content": ["a"]}]}
        )
        adapter = HttpSearchAdapter(session=session)

        result = await adapter.search(SearchQuery(text="test"), make_parameters())

        assert result.results[0].title.value == ""
        assert result.results[0].url.value == "42"
        assert result.results[0].content.value == "['a']"

    async def test_search_skips_malformed_result_entries(self) -> None:
        """Non-object entries in the results list are ignored."""
        session = make_session({"results": ["nonsense", {"title": "Real"}, None]})
        adapter = HttpSearchAdapter(session=session)

        result = await adapter.search(SearchQuery(text="test"), make_parameters())

        assert len(result.results) == 1
        assert result.results[0].title.value == "Real"

    async def test_malformed_entries_do_not_consume_the_max_results_budget(
        self,
    ) -> None:
        """Junk entries ahead of real ones must not crowd out valid results.

        Filtering must happen before the max_results slice, or a response with
        malformed entries first could return fewer results than actually exist.
        """
        session = make_session(
            {"results": ["junk"] * 5 + [{"title": f"Real{i}"} for i in range(3)]}
        )
        adapter = HttpSearchAdapter(session=session)

        result = await adapter.search(
            SearchQuery(text="test"), make_parameters(max_results=3)
        )

        assert [r.title.value for r in result.results] == ["Real0", "Real1", "Real2"]

    async def test_search_handles_missing_results_key(self) -> None:
        """A payload without a 'results' key yields an empty collection."""
        adapter = HttpSearchAdapter(session=make_session({}))

        result = await adapter.search(SearchQuery(text="test"), make_parameters())

        assert len(result.results) == 0

    async def test_search_handles_non_list_results_key(self) -> None:
        """A malformed 'results' value is treated as empty."""
        adapter = HttpSearchAdapter(session=make_session({"results": "oops"}))

        result = await adapter.search(SearchQuery(text="test"), make_parameters())

        assert len(result.results) == 0

    async def test_results_are_indexed_sequentially(self) -> None:
        """Result indices reflect ranking order starting at zero."""
        session = make_session({"results": [{"title": f"R{i}"} for i in range(3)]})
        adapter = HttpSearchAdapter(session=session)

        result = await adapter.search(SearchQuery(text="test"), make_parameters())

        assert [r.index.value for r in result.results] == [0, 1, 2]

    async def test_build_request_params_with_all_options(self) -> None:
        """Test building request parameters with all options."""
        session = make_session()
        adapter = HttpSearchAdapter(session=session)

        await adapter.search(
            SearchQuery(text="test query"),
            make_parameters(
                categories=("general", "news"),
                engines=("google", "bing", "duckduckgo"),
                language="fr",
                max_results=15,
                time_range="month",
            ),
        )

        params = sent_params(session)
        assert params["q"] == "test query"
        assert params["categories"] == "general,news"
        assert params["engines"] == "google,bing,duckduckgo"
        assert params["language"] == "fr"
        assert params["time_range"] == "month"
        assert params["format"] == "json"
        assert params["safesearch"] == 1
        assert params["pageno"] == 1

    async def test_build_request_params_without_optional_fields(self) -> None:
        """Test building request parameters without optional fields."""
        session = make_session()
        adapter = HttpSearchAdapter(session=session)

        await adapter.search(
            SearchQuery(text="simple"),
            make_parameters(categories=(), engines=()),
        )

        params = sent_params(session)
        assert "categories" not in params
        assert "engines" not in params
        assert "time_range" not in params

    async def test_execute_request_uses_correct_timeout(self) -> None:
        """Test that request uses correct timeout value."""
        session = make_session()
        adapter = HttpSearchAdapter(timeout=45, session=session)

        await adapter.search(SearchQuery(text="test"), make_parameters())

        assert session.get.call_args.kwargs["timeout"] == 45

    async def test_search_runs_off_the_event_loop_thread(self) -> None:
        """The blocking HTTP call is offloaded to a worker thread."""
        import threading

        calling_threads: list[int] = []

        def record_thread(*args: Any, **kwargs: Any) -> Mock:
            calling_threads.append(threading.get_ident())
            response = Mock()
            response.json.return_value = {"results": []}
            return response

        session = Mock(spec=requests.Session)
        session.get.side_effect = record_thread
        adapter = HttpSearchAdapter(session=session)

        await adapter.search(SearchQuery(text="test"), make_parameters())

        assert calling_threads and calling_threads[0] != threading.get_ident()

    async def test_concurrent_searches_overlap(self) -> None:
        """Concurrent searches must not serialize behind each other.

        Each request blocks for a fixed delay; if the event loop were blocked,
        total time would be the sum rather than roughly one delay.
        """
        import asyncio
        import threading
        import time

        delay = 0.2
        concurrency = 4
        in_flight = 0
        peak_in_flight = 0
        lock = threading.Lock()

        def slow_get(*args: Any, **kwargs: Any) -> Mock:
            nonlocal in_flight, peak_in_flight
            with lock:
                in_flight += 1
                peak_in_flight = max(peak_in_flight, in_flight)
            time.sleep(delay)
            with lock:
                in_flight -= 1
            response = Mock()
            response.json.return_value = {"results": []}
            return response

        session = Mock(spec=requests.Session)
        session.get.side_effect = slow_get
        adapter = HttpSearchAdapter(session=session)

        started = time.monotonic()
        await asyncio.gather(
            *[
                adapter.search(SearchQuery(text=f"q{i}"), make_parameters())
                for i in range(concurrency)
            ]
        )
        elapsed = time.monotonic() - started

        # Serialized execution would take concurrency * delay.
        assert elapsed < delay * concurrency * 0.75
        assert peak_in_flight > 1

    def test_close_releases_the_session(self) -> None:
        """close() shuts down the underlying connection pool."""
        session = make_session()
        HttpSearchAdapter(session=session).close()

        session.close.assert_called_once()
